# Solve one random instance with several algorithms and print the plans.
# Usage: python demo.py --n 10 --seed 3
import argparse

from truckload import (Params, TruckLoadingProblem, astar, describe, generate, genetic_algorithm,
                       simulated_annealing, ucs)


# Parse CLI args, generate one instance, run every algorithm, print each plan.
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dest", type=int, default=4)
    ap.add_argument("--capacity", type=int, default=4)
    ap.add_argument("--w-truck", type=float, default=3.0)
    a = ap.parse_args()
    params = Params(capacity=a.capacity, w_truck=a.w_truck)
    inst = generate(a.n, a.dest, a.seed, params)
    print("packages (id, arrival, dest):")
    print("  " + "  ".join(f"p{p.id}@{p.arrival:g}->{p.dest}" for p in inst.packages))
    for f in (ucs, astar):
        r = f(TruckLoadingProblem(inst))
        print(f"\n{r.algorithm}: expanded {r.expanded:,} nodes in {r.seconds:.3f}s [{r.status}]")
        if r.plan:
            print(describe(inst, r.plan))
    for r in (simulated_annealing(inst), genetic_algorithm(inst)):
        print(f"\n{r.algorithm}:")
        print(describe(inst, r.plan))


if __name__ == "__main__":
    main()
