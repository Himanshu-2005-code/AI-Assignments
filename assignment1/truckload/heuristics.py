"""Constructive baselines, online dispatch policies and local search.

These do not search the state space systematically; they are what you would
run when n is too large for A*, and they give the reference points
("how much does search buy us?").
"""
from __future__ import annotations

import math
import random
import time
from typing import List, Optional, Sequence, Tuple

from .problem import Instance, Trip, evaluate
from .search import SearchResult


def _res(name, inst, plan, evals, t0):
    r = evaluate(inst, plan)
    return SearchResult(name, plan, r.cost, evals, evals, time.perf_counter() - t0, "ok")


# --------------------------------------------------------------------------
# Online policy: no knowledge of future arrivals
# --------------------------------------------------------------------------
def online_policy(inst: Instance, max_wait: float = 2.0, respect_order: bool = True,
                  truck_wait: float = 0.0, block_ok: bool = False,
                  name: Optional[str] = None) -> SearchResult:
    """Event-driven rule a dispatcher could actually run.

    * A trip leaves when it is full, or ``max_wait`` after its first package
      was loaded (timeout).
    * A new package joins an open trip only if it does not block anybody:
      dest_new <= destination of the package currently at the door. Among
      those, the tightest fit (smallest door destination) is chosen - this is
      patience sorting, which uses the minimum number of LIFO-consistent stacks.
    * Otherwise, if ``block_ok``, it joins any open trip with room (accepting
      a rehandle rather than a new truck).
    * Otherwise it opens a trip on an idle truck; else on the truck returning
      first if that is at most ``truck_wait`` away; else on a new truck (if the
      fleet allows); else on the truck returning first anyway.
    """
    t0 = time.perf_counter()
    p = inst.params
    pk = inst.packages
    free: List[float] = []                 # per truck: back at depot
    open_: dict = {}                       # truck -> (ids list, deadline)
    plan: List[Trip] = []

    def close(k, depart_at):
        ids, _ = open_.pop(k)
        depart = max(free[k], pk[ids[-1]].arrival, depart_at)
        tr = Trip(k, tuple(ids), depart_at)
        plan.append(tr)
        # compute return time with the shared simulator
        from .problem import simulate_trip
        _, ret, _ = simulate_trip(inst, tr.ids, depart)
        free[k] = ret

    for pkg in pk:
        a = pkg.arrival
        for k in [k for k, (ids, dl) in open_.items() if dl < a]:
            close(k, open_[k][1])
        cands = []
        for k, (ids, dl) in open_.items():
            door = pk[ids[-1]].dest
            if len(ids) < p.capacity and (not respect_order or p.free_order or pkg.dest <= door):
                cands.append((door, k))
        roomy = [k for k, (ids, _) in open_.items() if len(ids) < p.capacity]
        idle = [k for k in range(len(free)) if k not in open_ and free[k] <= a]
        away = [k for k in range(len(free)) if k not in open_ and free[k] > a]
        soon = min(away, key=lambda k: free[k]) if away else None
        if cands:
            _, k = min(cands)
            open_[k][0].append(pkg.id)
        elif block_ok and roomy and not idle:
            k = min(roomy, key=lambda k: len(open_[k][0]))
            open_[k][0].append(pkg.id)
        else:
            if idle:
                k = idle[0]
            elif soon is not None and free[soon] - a <= truck_wait:
                k = soon
            elif p.max_trucks is None or len(free) < p.max_trucks:
                free.append(0.0)
                k = len(free) - 1
            else:
                busy = [k for k in range(len(free)) if k not in open_]
                if not busy:  # every truck has an open trip: send the fullest
                    k = max(open_, key=lambda k: len(open_[k][0]))
                    close(k, a)
                    busy = [k]
                k = min(busy, key=lambda k: free[k])
            open_[k] = ([pkg.id], max(a, free[k]) + max_wait)
        if len(open_[k][0]) == p.capacity:
            close(k, a)
    for k in list(open_):
        close(k, open_[k][1])
    # evaluator executes trips of one truck in plan order: already chronological
    return _res(name or f"Online(wait={max_wait:g})", inst, plan, 0, t0)


def immediate_dispatch(inst: Instance) -> SearchResult:
    """Every package leaves alone at once: minimum delay, many trucks."""
    return online_policy(inst, max_wait=0.0, name="Immediate")


def best_online(inst: Instance, waits: Sequence[float] = (0, 0.5, 1, 2, 3, 5),
                truck_waits: Sequence[float] = (0, 2, 4, 8, 1e9)) -> SearchResult:
    """Online policy with its knobs tuned per instance (an optimistic bound on
    what a tuned rule could do - in practice the knobs are tuned on history)."""
    t0 = time.perf_counter()
    best = min((online_policy(inst, w, truck_wait=tw, block_ok=b)
                for w in waits for tw in truck_waits for b in (False, True)), key=lambda r: r.cost)
    best.algorithm = "Online(tuned)"
    best.seconds = time.perf_counter() - t0
    return best


# --------------------------------------------------------------------------
# Local search over complete plans
# --------------------------------------------------------------------------
# Representation: truck[i] (truck id of package i) and brk[i] (package i starts
# a new trip on its truck). Packages of a truck, in arrival order, are cut into
# trips at brk flags and whenever a trip is full. This is exactly the space the
# tree search explores, so costs are directly comparable.

def decode(inst: Instance, truck: Sequence[int], brk: Sequence[int]) -> List[Trip]:
    cap = inst.params.capacity
    order = {}
    for t in truck:
        order.setdefault(t, len(order))
    trips: List[Trip] = []
    current = {}
    for i, t in enumerate(truck):
        tid = order[t]
        cur = current.get(tid)
        if cur is None or brk[i] or len(cur) == cap:
            cur = []
            current[tid] = cur
            trips.append((tid, cur))
        cur.append(i)
    return [Trip(tid, tuple(ids)) for tid, ids in trips]


def encode(inst: Instance, plan: Sequence[Trip]) -> Tuple[List[int], List[int]]:
    truck = [0] * inst.n
    brk = [0] * inst.n
    for tr in plan:
        for j in tr.ids:
            truck[j] = tr.truck
        brk[tr.ids[0]] = 1
    return truck, brk


def _cost(inst, truck, brk):
    return evaluate(inst, decode(inst, truck, brk)).cost


def _neighbours(inst, truck, brk):
    used = sorted(set(truck))
    new_id = max(used) + 1
    for i in range(inst.n):
        for t in used + [new_id]:
            if t != truck[i]:
                nt = list(truck)
                nt[i] = t
                yield nt, brk
        nb = list(brk)
        nb[i] ^= 1
        yield truck, nb
    for a in used:  # merge truck a into b
        for b in used:
            if a != b:
                yield [b if t == a else t for t in truck], brk


def hill_climbing(inst: Instance, restarts: int = 5, seed: int = 0,
                  start: Optional[List[Trip]] = None) -> SearchResult:
    """Steepest-ascent hill climbing with random restarts."""
    t0 = time.perf_counter()
    rng = random.Random(seed)
    evals = 0
    best = None
    for r in range(restarts):
        if r == 0 and start is not None:
            truck, brk = encode(inst, start)
        else:
            k = rng.randint(1, max(1, inst.n // 2))
            truck = [rng.randrange(k) for _ in range(inst.n)]
            brk = [int(rng.random() < 0.3) for _ in range(inst.n)]
        cur = _cost(inst, truck, brk)
        evals += 1
        while True:
            bc, bs = cur, None
            for nt, nb in _neighbours(inst, truck, brk):
                c = _cost(inst, nt, nb)
                evals += 1
                if c < bc - 1e-12:
                    bc, bs = c, (nt, nb)
            if bs is None:
                break
            truck, brk = bs
            cur = bc
        if best is None or cur < best[0]:
            best = (cur, truck, brk)
    return _res(f"HillClimb(r={restarts})", inst, decode(inst, best[1], best[2]), evals, t0)


def simulated_annealing(inst: Instance, iters: int = 20000, t_start: float = 2.0,
                        t_end: float = 0.01, seed: int = 0,
                        start: Optional[List[Trip]] = None) -> SearchResult:
    t0 = time.perf_counter()
    rng = random.Random(seed)
    if start is not None:
        truck, brk = encode(inst, start)
    else:
        truck, brk = [0] * inst.n, [0] * inst.n
    cur = _cost(inst, truck, brk)
    best = (cur, truck, brk)
    alpha = (t_end / t_start) ** (1.0 / iters)
    temp = t_start
    for _ in range(iters):
        used = sorted(set(truck))
        mv = rng.random()
        nt, nb = truck, brk
        i = rng.randrange(inst.n)
        if mv < 0.5:
            nt = list(truck)
            nt[i] = rng.choice(used + [max(used) + 1])
        elif mv < 0.9:
            nb = list(brk)
            nb[i] ^= 1
        elif len(used) > 1:
            a, b = rng.sample(used, 2)
            nt = [b if t == a else t for t in truck]
        c = _cost(inst, nt, nb)
        if c <= cur or rng.random() < math.exp(-(c - cur) / temp):
            truck, brk, cur = nt, nb, c
            if c < best[0]:
                best = (c, truck, brk)
        temp *= alpha
    return _res(f"SA(it={iters})", inst, decode(inst, best[1], best[2]), iters + 1, t0)
