# Problem definition: the data model, the random instance generator, and the
# plan evaluator (the single source of truth for scoring any plan).
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# One package: when it arrived, and which stop it's going to.
@dataclass(frozen=True)
class Package:
    id: int
    arrival: float
    dest: int


# Fixed knobs for one problem instance.
@dataclass(frozen=True)
class Params:
    capacity: int = 4                 # packages per trip
    tau: float = 1.0                  # travel time between consecutive stops
    w_truck: float = 3.0              # cost of one truck
    w_delay: float = 1.0              # cost of one unit of average delay
    max_trucks: Optional[int] = None  # fixed fleet size (None = unlimited)


# One randomly generated problem: its packages, its params, and how many stops exist.
@dataclass(frozen=True)
class Instance:
    packages: Tuple[Package, ...]
    params: Params
    num_dest: int

    @property
    def n(self) -> int:
        return len(self.packages)


# One truck's one trip: which packages, in load order, and when it's loaded.
@dataclass
class Trip:
    truck: int
    ids: Tuple[int, ...]               # package ids, in load order (non-increasing destination)
    depart_at: Optional[float] = None  # earliest allowed departure (online policies)


# The score of one complete plan, plus (optionally) the schedule that produced it.
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


# Build one random instance: n packages, one arriving per tick, destinations random.
def generate(n: int, num_dest: int = 4, seed: int = 0,
             params: Params = Params(), dest_weights: Optional[Sequence[float]] = None) -> Instance:
    rng = random.Random(seed)
    pkgs = []
    dests = list(range(1, num_dest + 1))
    for i in range(n):
        d = rng.choices(dests, weights=dest_weights)[0] if dest_weights else rng.choice(dests)
        pkgs.append(Package(i, float(i), d))  # package i arrives at tick i
    return Instance(tuple(pkgs), params, num_dest)


# Build an instance from an explicit list of arrival times and destinations.
def from_lists(arrivals: Sequence[float], dests: Sequence[int], params: Params = Params()) -> Instance:
    pkgs = tuple(Package(i, float(a), int(d)) for i, (a, d) in enumerate(zip(arrivals, dests)))
    assert all(pkgs[i].arrival <= pkgs[i + 1].arrival for i in range(len(pkgs) - 1)), "sort by arrival"
    return Instance(pkgs, params, max(dests))


# Drive one trip out and back; return each package's delivery time and the truck's return time.
def simulate_trip(inst: Instance, ids: Sequence[int], depart: float):
    p = inst.params
    pk = inst.packages
    t, pos = depart, 0           # t = current time, pos = current stop
    delivered: Dict[int, float] = {}
    for s in sorted({pk[j].dest for j in ids}):   # visit each stop in increasing order
        t += (s - pos) * p.tau
        pos = s
        for j in ids:
            if pk[j].dest == s:
                delivered[j] = t
    return delivered, t + pos * p.tau   # (delivery times, time back at the depot)


# Total delay (delivered - arrival) summed over one trip's packages.
def trip_delay_sum(inst: Instance, ids: Sequence[int], depart: float):
    delivered, ret = simulate_trip(inst, ids, depart)
    return sum(delivered[j] - inst.packages[j].arrival for j in ids), ret


# Score a complete plan: validates it, then computes trucks/avg delay/cost.
def evaluate(inst: Instance, plan: Sequence[Trip], keep_schedule: bool = False) -> Result:
    p = inst.params
    pk = inst.packages
    seen = sorted(j for tr in plan for j in tr.ids)
    if seen != list(range(inst.n)):
        raise ValueError("plan must deliver every package exactly once")
    free: Dict[int, float] = {}     # truck id -> time it's next free
    delays: Dict[int, float] = {}   # package id -> its delivery delay
    schedule = []
    for tr in plan:
        if len(tr.ids) > p.capacity:
            raise ValueError("trip exceeds capacity")
        prev_dest = None
        for j in tr.ids:   # hard rule: load order must be non-increasing destination
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


# Human-readable rendering of a plan's cost and truck-by-truck schedule.
def describe(inst: Instance, plan: Sequence[Trip]) -> str:
    r = evaluate(inst, plan, keep_schedule=True)
    lines = [r.short()]
    for s in r.schedule:
        load = " ".join(f"p{j}->{d}" for j, d in s["load"])
        lines.append(f"  truck {s['truck']}: depart {s['depart']:.1f} back {s['back']:.1f}  "
                     f"[deep .. door] {load}")
    return "\n".join(lines)
