# Runs the solver on ARC-AGI-1 tasks. Usage: python run.py <task_id> ...   or   python run.py --all
import json
import os
import sys

import numpy as np

from arc_solver.search import run_program, solve

DATA = os.environ.get("ARC_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks"))


# Load a task file into (demos, tests) lists of numpy grid pairs.
def load(task_id):
    with open(os.path.join(DATA, task_id + ".json")) as f:
        t = json.load(f)
    pair = lambda p: (np.array(p["input"]), np.array(p["output"]))
    return [pair(p) for p in t["train"]], [pair(p) for p in t["test"]]


# Solve one task and judge the program on the held-out test pair(s).
def run_task(task_id, max_depth=3, time_limit=20.0):
    demos, tests = load(task_id)
    res = solve(demos, max_depth, time_limit)
    res["task"] = task_id
    res["test_correct"] = False
    if res["solved"]:
        outs = [run_program(res["program"], ti, demos) for ti, _ in tests]
        res["test_correct"] = all(o is not None and o.shape == to.shape and (o == to).all()
                                  for o, (_, to) in zip(outs, tests))
    return res


if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids == ["--all"]:
        ids = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))
    for tid in ids:
        r = run_task(tid)
        status = "SOLVED+correct" if r["test_correct"] else ("fits demos, WRONG on test" if r["solved"] else "unsolved")
        print(f"{tid}: {status:<26} prog={r['program'] or r['best_program']} "
              f"nodes={r['expanded']} {r['seconds']:.1f}s" + (" TIMEOUT" if r["timeout"] else ""))
