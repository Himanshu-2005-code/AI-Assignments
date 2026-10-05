"""Sanity tests:  python -m pytest tests  (or python tests/test_truckload.py)"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from truckload import (Params, Trip, TruckLoadingProblem, astar, decode, evaluate, from_lists,
                       generate, genetic_algorithm, ucs)
from truckload.problem import simulate_trip


def test_rehandling_counts_blockers():
    inst = from_lists([0, 1, 2], [1, 3, 2], Params(rehandle=1.0))
    # load order 1,3,2 -> door holds dest 2, then 3, deepest dest 1
    delivered, ret, rh = simulate_trip(inst, (0, 1, 2), 0.0)
    assert rh == 2                       # at stop 1 both others block
    assert delivered[0] == 1 + 2         # drive 1 + 2 rehandles
    assert delivered[2] == 4             # stop 2: no blocker (dest 3 is deeper)
    assert ret == 3 + 2 + 3              # drive out 3 + rehandles 2 + back 3


def test_free_order_removes_rehandling():
    inst = from_lists([0, 1, 2], [1, 3, 2], Params(free_order=True))
    _, _, rh = simulate_trip(inst, (0, 1, 2), 0.0)
    assert rh == 0


def brute_force(inst):
    """Enumerate every (truck, break) encoding - the space the search explores."""
    n = inst.n
    best = float("inf")
    for truck in itertools.product(range(n), repeat=n):
        # canonical truck labels only
        seen, ok = {}, True
        for t in truck:
            if t not in seen:
                if t != len(seen):
                    ok = False
                    break
                seen[t] = 1
        if not ok:
            continue
        for brk in itertools.product((0, 1), repeat=n):
            best = min(best, evaluate(inst, decode(inst, truck, brk)).cost)
    return best


def test_optimal_algorithms_agree_with_brute_force():
    for seed in range(6):
        inst = generate(5, seed=seed, params=Params(capacity=3))
        bf = brute_force(inst)
        for alg in (ucs, astar):
            r = alg(TruckLoadingProblem(inst))
            assert abs(r.cost - bf) < 1e-9, (seed, r.algorithm, r.cost, bf)
            assert abs(evaluate(inst, r.plan).cost - r.cost) < 1e-9


def test_heuristics_admissible():
    for seed in range(5):
        inst = generate(7, seed=seed)
        P = TruckLoadingProblem(inst)
        opt = ucs(P).cost
        root = P.initial()
        assert P.h_open(root) <= opt + 1e-9
        assert P.h_remaining(root) <= P.h_open(root) + 1e-9


def test_fixed_fleet_respected():
    inst = generate(8, seed=2, params=Params(max_trucks=1))
    r = astar(TruckLoadingProblem(inst))
    assert evaluate(inst, r.plan).trucks == 1


def test_genetic_algorithm_valid_and_reasonable():
    for seed in range(3):
        inst = generate(8, seed=seed)
        opt = astar(TruckLoadingProblem(inst)).cost
        r = genetic_algorithm(inst, pop_size=30, generations=80, seed=seed)
        e = evaluate(inst, r.plan)       # raises if the plan is invalid
        assert abs(e.cost - r.cost) < 1e-9
        assert r.cost <= opt * 1.5 + 1e-9, (seed, r.cost, opt)  # GA isn't optimal, but shouldn't be far off


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
