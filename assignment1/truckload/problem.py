"""Problem definition, random instance generator and the plan evaluator.

Model (see README for the full discussion of assumptions):

* Packages arrive at the dispatch centre at known times ``arrival`` and carry an
  integer destination ``dest`` in 1..D.
* Destinations lie on one highway leaving the depot; stop ``k`` is ``k * tau``
  time units from the depot, consecutive stops are ``tau`` apart.
* All trucks are identical with capacity ``capacity``. A *trip* is one loading
  of a truck followed by a run out to its farthest stop and back.
* Packages are loaded into a truck in arrival order (load-on-arrival: no
  re-sorting on the floor). The last package loaded sits at the door, i.e. the
  truck is a stack. If a package for a later stop is in front of one for the
  current stop, it must be taken out and put back: ``rehandle`` time each.
  With ``free_order=True`` (a staging area exists) a trip is loaded in the best
  order (farthest destination first) and no rehandling ever happens.
* A trip departs at ``max(truck back at depot, last package of the trip has
  arrived, optional explicit depart_at)``.
* Objective: ``w_truck * #trucks + w_delay * mean(delivery time - arrival)``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Package:
    id: int
    arrival: float
    dest: int


@dataclass(frozen=True)
class Params:
    capacity: int = 4
    tau: float = 1.0          # travel time between consecutive stops
    unload: float = 0.0       # time to hand over one package at its stop
    rehandle: float = 0.5     # time to move one blocking package out and back in
    w_truck: float = 3.0      # weight of one truck assigned to the centre
    w_delay: float = 1.0      # weight of one time unit of average delivery time
    free_order: bool = False  # staging area: trips can be loaded in any order
    max_trucks: Optional[int] = None  # fixed fleet variant (None = unlimited)


@dataclass(frozen=True)
class Instance:
    packages: Tuple[Package, ...]
    params: Params
    num_dest: int

    @property
    def n(self) -> int:
        return len(self.packages)


@dataclass
class Trip:
    truck: int
    ids: Tuple[int, ...]               # package ids in load order (first = deepest)
    depart_at: Optional[float] = None  # earliest allowed departure (online policies)


@dataclass
class Result:
    cost: float
    trucks: int
    avg_delay: float
    max_delay: float
    rehandles: int
    trips: int
    schedule: List[dict] = field(default_factory=list)

    def short(self) -> str:
        return (f"cost={self.cost:.3f} trucks={self.trucks} trips={self.trips} "
                f"avg_delay={self.avg_delay:.3f} rehandles={self.rehandles}")


# --------------------------------------------------------------------------
# Instance generation
# --------------------------------------------------------------------------
def generate(n: int, num_dest: int = 4, rate: float = 2.0, seed: int = 0,
             params: Params = Params(), dest_weights: Optional[Sequence[float]] = None,
             resolution: float = 0.1) -> Instance:
    """Random instance: Poisson arrivals with ``rate`` packages per tau,
    destinations uniform (or drawn with ``dest_weights``)."""
    rng = random.Random(seed)
    t = 0.0
    pkgs = []
    dests = list(range(1, num_dest + 1))
    for i in range(n):
        t += rng.expovariate(rate)
        d = rng.choices(dests, weights=dest_weights)[0] if dest_weights else rng.choice(dests)
        pkgs.append(Package(i, round(round(t / resolution) * resolution, 6), d))
    return Instance(tuple(pkgs), params, num_dest)


def from_lists(arrivals: Sequence[float], dests: Sequence[int], params: Params = Params()) -> Instance:
    pkgs = tuple(Package(i, float(a), int(d)) for i, (a, d) in enumerate(zip(arrivals, dests)))
    assert all(pkgs[i].arrival <= pkgs[i + 1].arrival for i in range(len(pkgs) - 1)), "sort by arrival"
    return Instance(pkgs, params, max(dests))


# --------------------------------------------------------------------------
# Trip simulation
# --------------------------------------------------------------------------
def load_order(inst: Instance, ids: Iterable[int]) -> List[int]:
    ids = list(ids)
    if inst.params.free_order:
        ids.sort(key=lambda j: -inst.packages[j].dest)  # farthest first = deepest
    return ids


def simulate_trip(inst: Instance, ids: Sequence[int], depart: float):
    """Drive one trip. Returns (delivery time per id, return time, #rehandles)."""
    p = inst.params
    pk = inst.packages
    stack = load_order(inst, ids)  # index -1 is at the door
    t, pos, rehandles = depart, 0, 0
    delivered: Dict[int, float] = {}
    for s in sorted({pk[j].dest for j in stack}):
        t += (s - pos) * p.tau
        pos = s
        first = next(k for k, j in enumerate(stack) if pk[j].dest == s)  # deepest one
        here = [j for j in stack if pk[j].dest == s]
        blockers = len(stack) - first - len(here)  # others in front of the deepest
        t += blockers * p.rehandle + len(here) * p.unload
        rehandles += blockers
        for j in here:
            delivered[j] = t
        stack = [j for j in stack if pk[j].dest != s]
    return delivered, t + pos * p.tau, rehandles


def trip_delay_sum(inst: Instance, ids: Sequence[int], depart: float):
    delivered, ret, rh = simulate_trip(inst, ids, depart)
    return sum(delivered[j] - inst.packages[j].arrival for j in ids), ret, rh


# --------------------------------------------------------------------------
# Plan evaluation (single source of truth for every algorithm)
# --------------------------------------------------------------------------
def evaluate(inst: Instance, plan: Sequence[Trip], keep_schedule: bool = False) -> Result:
    """Trips of the same truck are executed in the order they appear in ``plan``."""
    p = inst.params
    pk = inst.packages
    seen = sorted(j for tr in plan for j in tr.ids)
    if seen != list(range(inst.n)):
        raise ValueError("plan must deliver every package exactly once")
    free: Dict[int, float] = {}
    delays: Dict[int, float] = {}
    rehandles = 0
    schedule = []
    for tr in plan:
        if len(tr.ids) > p.capacity:
            raise ValueError("trip exceeds capacity")
        depart = max(free.get(tr.truck, 0.0), max(pk[j].arrival for j in tr.ids))
        if tr.depart_at is not None:
            depart = max(depart, tr.depart_at)
        delivered, ret, rh = simulate_trip(inst, tr.ids, depart)
        free[tr.truck] = ret
        rehandles += rh
        for j in tr.ids:
            delays[j] = delivered[j] - pk[j].arrival
        if keep_schedule:
            schedule.append(dict(truck=tr.truck, load=[(j, pk[j].dest) for j in load_order(inst, tr.ids)],
                                 depart=depart, back=ret, rehandles=rh))
    trucks = len(free)
    if p.max_trucks is not None and trucks > p.max_trucks:
        raise ValueError("fleet size exceeded")
    avg = sum(delays.values()) / inst.n
    cost = p.w_truck * trucks + p.w_delay * avg
    return Result(cost, trucks, avg, max(delays.values()), rehandles, len(plan), schedule)


def describe(inst: Instance, plan: Sequence[Trip]) -> str:
    r = evaluate(inst, plan, keep_schedule=True)
    lines = [r.short()]
    for s in r.schedule:
        load = " ".join(f"p{j}->{d}" for j, d in s["load"])
        lines.append(f"  truck {s['truck']}: depart {s['depart']:.1f} back {s['back']:.1f} "
                     f"rehandles {s['rehandles']}  [deep .. door] {load}")
    return "\n".join(lines)
