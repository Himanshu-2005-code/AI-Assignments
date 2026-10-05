"""Local search over complete plans: Simulated Annealing and the Genetic
Algorithm, both taught in lecture (Sep 3 and Sep 10 respectively).

These do not search the state space systematically; they are what you would
run when n is too large for A*, and they give the reference points ("how
much does search buy us?").

Representation: truck[i] (truck id of package i) and brk[i] (package i
starts a new trip on its truck). Packages of a truck, in arrival order, are
cut into trips at brk flags and whenever a trip is full. This is exactly the
space the tree search explores, so costs compare directly against A*/UCS.
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


def _random_individual(inst, rng):
    k = rng.randint(1, max(1, inst.n // 2))
    truck = [rng.randrange(k) for _ in range(inst.n)]
    brk = [int(rng.random() < 0.3) for _ in range(inst.n)]
    return truck, brk


# --------------------------------------------------------------------------
# Simulated Annealing (Sep 3): perturb one full candidate, accept a worse
# move with probability exp(-delta/T), cool T over the run.
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Genetic Algorithm (Sep 10): population of N candidates, keep the best N/2,
# sample pairs from the survivors, crossover to make N/2 children, new
# population = survivors + children. Mutation nudges a child off its
# parents' exact encoding, same as the course's forward-pointer to
# "Evolutionary (Genetic) Search" variants.
# --------------------------------------------------------------------------
def genetic_algorithm(inst: Instance, pop_size: int = 40, generations: int = 200,
                      mutation_rate: float = 0.1, seed: int = 0,
                      start: Optional[List[Trip]] = None) -> SearchResult:
    t0 = time.perf_counter()
    rng = random.Random(seed)
    evals = 0

    def fitness(ind):
        nonlocal evals
        evals += 1
        return _cost(inst, ind[0], ind[1])

    def crossover(p1, p2):
        t1, b1 = p1
        t2, b2 = p2
        cut = rng.randrange(1, inst.n) if inst.n > 1 else 1
        return t1[:cut] + t2[cut:], b1[:cut] + b2[cut:]

    def mutate(ind):
        truck, brk = list(ind[0]), list(ind[1])
        used = sorted(set(truck))
        new_id = max(used) + 1
        for i in range(inst.n):
            if rng.random() < mutation_rate:
                truck[i] = rng.choice(used + [new_id])
            if rng.random() < mutation_rate:
                brk[i] ^= 1
        return truck, brk

    population = [_random_individual(inst, rng) for _ in range(pop_size)]
    if start is not None:
        population[0] = encode(inst, start)

    best = None
    for _ in range(generations):
        scored = sorted(((fitness(ind), ind) for ind in population), key=lambda x: x[0])
        if best is None or scored[0][0] < best[0]:
            best = scored[0]
        survivors = [ind for _, ind in scored[:max(2, pop_size // 2)]]
        children = []
        while len(survivors) + len(children) < pop_size:
            p1, p2 = rng.sample(survivors, 2)
            children.append(mutate(crossover(p1, p2)))
        population = survivors + children

    return _res(f"GA(pop={pop_size},gen={generations})", inst,
               decode(inst, best[1][0], best[1][1]), evals, t0)
