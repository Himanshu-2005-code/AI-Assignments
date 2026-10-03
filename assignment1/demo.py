"""Solve one random instance with several algorithms and print the plans.

    python demo.py --n 10 --seed 3
"""
import argparse

from truckload import (Params, TruckLoadingProblem, astar, best_online, describe, dfbnb, generate,
                       simulated_annealing, ucs, weighted_astar)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dest", type=int, default=4)
    ap.add_argument("--rate", type=float, default=2.0)
    ap.add_argument("--capacity", type=int, default=4)
    ap.add_argument("--w-truck", type=float, default=3.0)
    ap.add_argument("--free-order", action="store_true", help="staging area: any load order")
    a = ap.parse_args()
    params = Params(capacity=a.capacity, w_truck=a.w_truck, free_order=a.free_order)
    inst = generate(a.n, a.dest, a.rate, a.seed, params)
    print("packages (id, arrival, dest):")
    print("  " + "  ".join(f"p{p.id}@{p.arrival:g}->{p.dest}" for p in inst.packages))
    for f in (ucs, astar, dfbnb, lambda P: weighted_astar(P, 2.0)):
        r = f(TruckLoadingProblem(inst))
        print(f"\n{r.algorithm}: expanded {r.expanded:,} nodes in {r.seconds:.3f}s [{r.status}]")
        if r.plan:
            print(describe(inst, r.plan))
    for r in (simulated_annealing(inst), best_online(inst)):
        print(f"\n{r.algorithm}:")
        print(describe(inst, r.plan))


if __name__ == "__main__":
    main()
