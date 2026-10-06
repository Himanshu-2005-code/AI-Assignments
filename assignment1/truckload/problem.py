"""Problem definition, random instance generator and the plan evaluator.

Model (see README for the full discussion of assumptions):

* Packages arrive at the dispatch centre at known times ``arrival`` and carry an
  integer destination ``dest`` in 1..D.
* Destinations lie on one highway leaving the depot; stop ``k`` is ``k * tau``
  time units from the depot, consecutive stops are ``tau`` apart.
* All trucks are identical with capacity ``capacity``. A *trip* is one loading
  of a truck followed by a run out to its farthest stop and back.
* Packages unload from the front of the truck, so within one trip they must be
  loaded with non-increasing destinations (the next stop's package is always
  nearest the door). This is enforced as a hard rule on which packages a trip
  may accept, not a cost to pay afterwards: if the next package waiting would
  need to come out before one already loaded, that trip simply cannot take it,
  and it has to start a new trip (or a new truck) instead.
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
    w_truck: float = 3.0      # weight of one truck assigned to the centre
    w_delay: float = 1.0      # weight of one time unit of average delivery time
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
    ids: Tuple[int, ...]               # package ids, in load order (non-increasing destination)
    depart_at: Optional[float] = None  # earliest allowed departure (online policies)


@dataclass
class Result:
    cost: float
    trucks: int
    avg_delay: float
    max_delay: float
    trips: int
    schedule: List[dict] = field(default_factory=list)

    def short(self) -> str:
        return (f"cost={self.cost:.3f} trucks={self.trucks} trips={self.trips} "
                f"avg_delay={self.avg_delay:.3f}")


# --------------------------------------------------------------------------
# Instance generation
# --------------------------------------------------------------------------
def generate(n: int, num_dest: int = 4, seed: int = 0,
             params: Params = Params(), dest_weights: Optional[Sequence[float]] = None) -> Instance:
    """Random instance: n packages, one arriving per tick (0, 1, 2, ...), with a
    random sequence of destinations (uniform, or drawn with ``dest_weights``).
    The only randomness is which destination lands at which arrival position -
    package arrival order and spacing are otherwise just a fixed count-up."""
    rng = random.Random(seed)
    pkgs = []
    dests = list(range(1, num_dest + 1))
    for i in range(n):
        d = rng.choices(dests, weights=dest_weights)[0] if dest_weights else rng.choice(dests)
        pkgs.append(Package(i, float(i), d))
    return Instance(tuple(pkgs), params, num_dest)


def from_lists(arrivals: Sequence[float], dests: Sequence[int], params: Params = Params()) -> Instance:
    pkgs = tuple(Package(i, float(a), int(d)) for i, (a, d) in enumerate(zip(arrivals, dests)))
    assert all(pkgs[i].arrival <= pkgs[i + 1].arrival for i in range(len(pkgs) - 1)), "sort by arrival"
    return Instance(pkgs, params, max(dests))


# --------------------------------------------------------------------------
# Trip simulation
# --------------------------------------------------------------------------
def simulate_trip(inst: Instance, ids: Sequence[int], depart: float):
    """Drive one trip out along the highway and back. ``ids`` is already in
    load order (non-increasing destination), so the truck never has to dig
    for a package - it simply unloads whoever is at the door at each stop.
    Returns (delivery time per id, return time)."""
    p = inst.params
    pk = inst.packages
    t, pos = depart, 0
    delivered: Dict[int, float] = {}
    for s in sorted({pk[j].dest for j in ids}):
        t += (s - pos) * p.tau
        pos = s
        for j in ids:
            if pk[j].dest == s:
                delivered[j] = t
    return delivered, t + pos * p.tau


def trip_delay_sum(inst: Instance, ids: Sequence[int], depart: float):
    delivered, ret = simulate_trip(inst, ids, depart)
    return sum(delivered[j] - inst.packages[j].arrival for j in ids), ret


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
    schedule = []
    for tr in plan:
        if len(tr.ids) > p.capacity:
            raise ValueError("trip exceeds capacity")
        prev_dest = None
        for j in tr.ids:
            d = pk[j].dest
            if prev_dest is not None and d > prev_dest:
                raise ValueError("trip loads a farther package behind a nearer one")
            prev_dest = d
        depart = max(free.get(tr.truck, 0.0), max(pk[j].arrival for j in tr.ids))
        if tr.depart_at is not None:
            depart = max(depart, tr.depart_at)
        delivered, ret = simulate_trip(inst, tr.ids, depart)
        free[tr.truck] = ret
        for j in tr.ids:
            delays[j] = delivered[j] - pk[j].arrival
        if keep_schedule:
            schedule.append(dict(truck=tr.truck, load=[(j, pk[j].dest) for j in tr.ids],
                                 depart=depart, back=ret))
    trucks = len(free)
    if p.max_trucks is not None and trucks > p.max_trucks:
        raise ValueError("fleet size exceeded")
    avg = sum(delays.values()) / inst.n
    cost = p.w_truck * trucks + p.w_delay * avg
    return Result(cost, trucks, avg, max(delays.values()), len(plan), schedule)


def describe(inst: Instance, plan: Sequence[Trip]) -> str:
    r = evaluate(inst, plan, keep_schedule=True)
    lines = [r.short()]
    for s in r.schedule:
        load = " ".join(f"p{j}->{d}" for j, d in s["load"])
        lines.append(f"  truck {s['truck']}: depart {s['depart']:.1f} back {s['back']:.1f}  "
                     f"[deep .. door] {load}")
    return "\n".join(lines)
