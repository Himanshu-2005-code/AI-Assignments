# Search for a program (sequence of DSL actions) that turns every demo input into its demo output.
# State = the tuple of grids you get by running the program so far on ALL demo inputs at once.
# Goal test = all of those grids equal the demo outputs. Breadth-first with a visited set.
import time
from collections import deque

import numpy as np

from .dsl import build_actions

MAX_GRID = 30


# Hashable key of a grid (shape + bytes) so equal grids are detected.
def gkey(g):
    return (g.shape, g.tobytes())


# Number of cells that differ (shape mismatch counts as a full miss). Used to rank partial answers.
def mismatch(g, target):
    if g.shape != target.shape:
        return target.size + g.size
    return int((g != target).sum())


# Apply one action safely: failures or oversize outputs return None (the branch is dead).
def safe_apply(fn, g):
    try:
        out = fn(g)
    except Exception:
        return None
    if out.ndim != 2 or out.size == 0 or max(out.shape) > MAX_GRID:
        return None
    return np.ascontiguousarray(out)


# BFS over programs. Returns dict(program, expanded, seconds, solved, best_program, best_error).
def solve(demos, max_depth=3, time_limit=20.0):
    acts = build_actions(demos)
    start = tuple(i for i, _ in demos)
    targets = [o for _, o in demos]
    t0 = time.time()
    seen = {tuple(gkey(g) for g in start)}
    queue = deque([(start, ())])
    expanded = 0
    best = (sum(mismatch(g, t) for g, t in zip(start, targets)), ())
    while queue:
        grids, prog = queue.popleft()
        if len(prog) >= max_depth:
            continue
        for name, fn in acts.items():
            if time.time() - t0 > time_limit:
                return dict(solved=False, program=None, expanded=expanded, seconds=time.time() - t0,
                            best_program=best[1], best_error=best[0], timeout=True)
            nxt = []
            for g in grids:
                out = safe_apply(fn, g)
                if out is None:
                    break
                nxt.append(out)
            else:
                expanded += 1
                key = tuple(gkey(g) for g in nxt)
                if key in seen:
                    continue
                seen.add(key)
                new_prog = prog + (name,)
                err = sum(mismatch(g, t) for g, t in zip(nxt, targets))
                if err == 0:
                    return dict(solved=True, program=new_prog, expanded=expanded, seconds=time.time() - t0,
                                best_program=new_prog, best_error=0, timeout=False)
                if err < best[0]:
                    best = (err, new_prog)
                queue.append((tuple(nxt), new_prog))
    return dict(solved=False, program=None, expanded=expanded, seconds=time.time() - t0,
                best_program=best[1], best_error=best[0], timeout=False)


# Run a program (tuple of action names) on a grid.
def run_program(program, grid, demos):
    acts = build_actions(demos)
    g = grid
    for name in program:
        g = safe_apply(acts[name], g)
        if g is None:
            return None
    return g
