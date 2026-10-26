# Runs the solver on all 400 ARC-AGI-1 training tasks (5 s limit each) and prints the totals.
# Usage: ARC_DATA=<path to ARC-AGI/data/training> python benchmark_all.py
import os
import sys

from run import DATA, run_task

if __name__ == "__main__":
    ids = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))
    solved = overfit = 0
    for tid in ids:
        r = run_task(tid, max_depth=3, time_limit=5.0)
        if r["test_correct"]:
            solved += 1
        elif r["solved"]:
            overfit += 1
        print(tid, "OK" if r["test_correct"] else ("OVERFIT" if r["solved"] else "no"), r["program"] or "", flush=True)
    print(f"correct {solved}/{len(ids)}, fit demos but wrong on test {overfit}")
