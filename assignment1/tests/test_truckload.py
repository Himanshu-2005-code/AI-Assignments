"""Sanity tests:  python -m pytest tests  (or python tests/test_truckload.py)"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from truckload import (Params, Trip, TruckLoadingProblem, astar, decode, evaluate, from_lists,
                       generate, genetic_algorithm, ucs)
from truckload.problem import simulate_trip


def test_valid_order_delivers_nearest_stop_first():
    # Loaded deepest-to-door as 3,2,1 (non-increasing) - a valid trip. The
    # truck should unload dest 1 first, then 2, then 3, with no shuffling.
    inst = from_lists([0, 0, 0], [3, 2, 1])
    delivered, ret = simulate_trip(inst, (0, 1, 2), 0.0)
    assert delivered[2] == 1   # dest 1, reached first
    assert delivered[1] == 2   # dest 2
    assert delivered[0] == 3   # dest 3
    assert ret == 6            # drive out 3 + back 3, no extra cost anywhere


def test_out_of_order_trip_is_rejected():
    # Loaded 1 then 3: the package for the farther stop (3) ends up behind
    # the one for the nearer stop (1), so it can't come out first. The
    # assignment's "respect the ordering" rule makes this plan invalid
    # outright, not merely penalised.
    inst = from_lists([0, 1], [1, 3])
    try:
        evaluate(inst, [Trip(0, (0, 1))])
        assert False, "expected a ValueError for an out-of-order trip"
    except ValueError:
        pass


def brute_force(inst):
    """Enumerate every (truck, break) encoding - the space the search explores.
    An encoding that decodes into an out-of-order trip is invalid and skipped,
    exactly like the tree search never offering that APPEND action."""
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
            try:
                best = min(best, evaluate(inst, decode(inst, truck, brk)).cost)
            except ValueError:
                continue
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
