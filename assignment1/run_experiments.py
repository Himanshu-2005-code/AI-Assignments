"""Run every experiment of the report and write tables/plots to results/.

    python run_experiments.py            # full run (a few minutes)
    python run_experiments.py --quick    # fewer seeds, smaller sizes
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
from dataclasses import replace
from multiprocessing import Pool

from truckload import (Params, TruckLoadingProblem, astar, beam_search, bfs, dfs, evaluate,
                       generate, genetic_algorithm, greedy, simulated_annealing, ucs)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
LIMIT = 200_000  # node limit for the exhaustive / tree searches


def algorithms(small: bool):
    algs = {
        "A*(h_open)": lambda P, I: astar(P, "h_open", node_limit=LIMIT),
        "Greedy-BeFS": lambda P, I: greedy(P, node_limit=LIMIT),
        "Beam(k=5)": lambda P, I: beam_search(P, 5),
        "Beam(k=25)": lambda P, I: beam_search(P, 25),
        "SA(20k)": lambda P, I: simulated_annealing(I, 20000),
        "GA(pop=40,gen=200)": lambda P, I: genetic_algorithm(I, 40, 200),
    }
    if small:
        algs.update({
            "BFS": lambda P, I: bfs(P, node_limit=LIMIT),
            "DFS": lambda P, I: dfs(P, node_limit=LIMIT),
            "UCS": lambda P, I: ucs(P, node_limit=LIMIT),
            "A*(h_rem)": lambda P, I: astar(P, "h_rem", node_limit=LIMIT),
        })
    return algs


ORDER = ["BFS", "DFS", "UCS", "A*(h_rem)", "A*(h_open)", "Greedy-BeFS", "Beam(k=5)",
         "Beam(k=25)", "SA(20k)", "GA(pop=40,gen=200)"]


def run_one(args):
    n, seed, small = args
    inst = generate(n, seed=seed)
    rows = []
    for name, f in algorithms(small).items():
        P = TruckLoadingProblem(inst)
        r = f(P, inst)
        ev = evaluate(inst, r.plan) if r.plan else None
        rows.append(dict(n=n, seed=seed, alg=name, status=r.status, cost=r.cost if ev else None,
                         expanded=r.expanded, seconds=r.seconds,
                         trucks=ev.trucks if ev else None, delay=ev.avg_delay if ev else None))
    return rows


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else float("nan")


def exp_algorithms(pool, sizes, seeds, small, tag):
    rows = [r for rs in pool.map(run_one, [(n, s, small) for n in sizes for s in range(seeds)]) for r in rs]
    # reference = optimal (A* finished) else best found by anyone
    ref = {}
    for r in rows:
        k = (r["n"], r["seed"])
        if r["cost"] is not None:
            ref[k] = min(ref.get(k, float("inf")), r["cost"])
    opt = {(r["n"], r["seed"]) for r in rows if r["alg"] == "A*(h_open)" and r["status"] == "ok"}
    for r in rows:
        r["gap"] = None if r["cost"] is None else 100 * (r["cost"] - ref[(r["n"], r["seed"])]) / ref[(r["n"], r["seed"])]
        r["hit"] = r["gap"] is not None and r["gap"] < 1e-6
    with open(os.path.join(OUT, f"{tag}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    lines = []
    for n in sizes:
        sub = [r for r in rows if r["n"] == n]
        nopt = sum(1 for s in range(seeds) if (n, s) in opt)
        lines.append(f"\n**n = {n}** (reference = optimum on {nopt}/{seeds} instances, else best found)\n")
        tab = []
        for a in ORDER:
            rs = [r for r in sub if r["alg"] == a]
            if not rs:
                continue
            solved = sum(r["status"] == "ok" and r["cost"] is not None for r in rs)
            tab.append([a, f"{solved}/{len(rs)}", f"{mean([r['gap'] for r in rs]):.1f}",
                        f"{sum(r['hit'] for r in rs)}/{len(rs)}",
                        f"{mean([r['expanded'] for r in rs]):,.0f}", f"{mean([r['seconds'] for r in rs]):.3f}",
                        f"{mean([r['trucks'] for r in rs]):.2f}", f"{mean([r['delay'] for r in rs]):.2f}"])
        lines.append(md_table(["algorithm", "finished", "gap %", "best hit", "nodes expanded*",
                               "time s", "trucks", "avg delay"], tab))
    lines.append("\n*for local search / online rules: number of complete plans evaluated (0 for rules).")
    return "\n".join(lines), rows


def _heur_job(args):
    n, seed = args
    inst = generate(n, seed=seed)
    out = {}
    for name, f in [("UCS", lambda P: ucs(P, node_limit=LIMIT)),
                    ("A*(h_rem)", lambda P: astar(P, "h_rem", node_limit=LIMIT)),
                    ("A*(h_open)", lambda P: astar(P, "h_open", node_limit=LIMIT))]:
        r = f(TruckLoadingProblem(inst))
        out[name] = r.expanded if r.status == "ok" else None
    return n, out


def exp_heuristics(pool, sizes, seeds):
    res = pool.map(_heur_job, [(n, s) for n in sizes for s in range(seeds)])
    names = ["UCS", "A*(h_rem)", "A*(h_open)"]
    tab, series = [], {k: [] for k in names}
    for n in sizes:
        row = [n]
        for k in names:
            vals = [o[k] for m, o in res if m == n]
            ok = [v for v in vals if v is not None]
            gm = st.geometric_mean(ok) if len(ok) == len(vals) else None
            series[k].append(gm)
            row.append(f"{gm:,.0f}" if gm else f"> limit ({len(ok)}/{len(vals)} done)")
        tab.append(row)
    return md_table(["n"] + [f"{k} (geo-mean expanded)" for k in names], tab), sizes, series


def _variant_job(args):
    name, n, seed, kind, kw = args
    base = Params()
    if kind == "params":
        inst = generate(n, seed=seed, params=replace(base, **kw))
        r = astar(TruckLoadingProblem(inst), node_limit=LIMIT)
    elif kind == "gen":
        inst = generate(n, seed=seed, **kw)
        r = astar(TruckLoadingProblem(inst), node_limit=LIMIT)
    elif kind == "ga":
        inst = generate(n, seed=seed)
        r = genetic_algorithm(inst, **kw)
    if r.plan is None:
        return name, None
    e = evaluate(inst, r.plan)
    return name, (e.cost, e.trucks, e.avg_delay, e.trips)


def exp_variants(pool, n, seeds):
    variants = [
        ("Base: offline optimum (A*)", "params", {}),
        ("Bigger trucks (capacity 6)", "params", {"capacity": 6}),
        ("Smaller trucks (capacity 2)", "params", {"capacity": 2}),
        ("Fixed fleet of 1 truck", "params", {"max_trucks": 1}),
        ("Busier centre (rate 4/tau)", "gen", {"rate": 4.0}),
        ("Quieter centre (rate 1/tau)", "gen", {"rate": 1.0}),
        ("Skewed destinations (near-heavy)", "gen", {"dest_weights": [4, 3, 2, 1]}),
        ("Genetic Algorithm (pop=40, gen=200)", "ga", {"pop_size": 40, "generations": 200}),
        ("Genetic Algorithm, smaller population (pop=10, gen=200)", "ga", {"pop_size": 10, "generations": 200}),
    ]
    res = pool.map(_variant_job, [(nm, n, s, k, kw) for nm, k, kw in variants for s in range(seeds)])
    tab = []
    for nm, _, _ in variants:
        vals = [v for m, v in res if m == nm and v is not None]
        tot = sum(1 for m, _ in res if m == nm)
        tab.append([nm, f"{len(vals)}/{tot}"] + [f"{mean([v[i] for v in vals]):.2f}" for i in range(4)])
    return md_table(["variant", "solved", "cost", "trucks", "avg delay", "trips"], tab)


def _weight_job(args):
    w, n, seed = args
    inst = generate(n, seed=seed, params=replace(Params(), w_truck=w))
    r = astar(TruckLoadingProblem(inst), node_limit=LIMIT)
    e = evaluate(inst, r.plan)
    return w, e.trucks, e.avg_delay


def exp_weights(pool, n, seeds, weights):
    res = pool.map(_weight_job, [(w, n, s) for w in weights for s in range(seeds)])
    tab, xs, ys = [], [], []
    for w in weights:
        t = mean([r[1] for r in res if r[0] == w])
        d = mean([r[2] for r in res if r[0] == w])
        tab.append([w, f"{t:.2f}", f"{d:.2f}"])
        xs.append(t)
        ys.append(d)
    return md_table(["w_truck (w_delay=1)", "trucks", "avg delay"], tab), weights, xs, ys


def plots(heur, weights, alg_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - skipping plots")
        return
    sizes, series = heur
    fig, ax = plt.subplots(figsize=(6, 4))
    for k, v in series.items():
        pts = [(n, y) for n, y in zip(sizes, v) if y]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=k)
    ax.set_yscale("log")
    ax.set_xlabel("number of packages n")
    ax.set_ylabel("nodes expanded (geometric mean)")
    ax.set_title("Effect of the heuristic on search effort")
    ax.grid(True, which="both", alpha=.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "heuristics_nodes.png"), dpi=130)

    ws, xs, ys = weights
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(xs, ys, marker="o")
    for w, x, y in zip(ws, xs, ys):
        ax.annotate(f"w={w:g}", (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel("trucks used (mean)")
    ax.set_ylabel("average delivery time (mean)")
    ax.set_title("Trade-off traced by the truck weight")
    ax.grid(True, alpha=.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "weight_tradeoff.png"), dpi=130)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for a in ORDER:
        rs = [r for r in alg_rows if r["alg"] == a and r["cost"] is not None and r["expanded"]]
        if rs:
            ax.scatter(mean([r["expanded"] for r in rs]), mean([r["gap"] for r in rs]), label=a)
    ax.set_xscale("log")
    ax.set_xlabel("nodes expanded / plans evaluated (mean)")
    ax.set_ylabel("cost gap to best known (%)")
    ax.set_title("Quality vs effort (large instances)")
    ax.grid(True, which="both", alpha=.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "quality_vs_effort.png"), dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    seeds = 4 if a.quick else 10
    small = [4, 6, 8] if a.quick else [4, 6, 8, 10]
    large = [12, 16] if a.quick else [12, 16, 20, 30]
    with Pool() as pool:
        t1, _ = exp_algorithms(pool, small, seeds, True, "algorithms_small")
        t2, rows_large = exp_algorithms(pool, large, seeds, False, "algorithms_large")
        t3, hs, hser = exp_heuristics(pool, [4, 6, 8, 10, 12, 14] if not a.quick else [4, 6, 8], seeds)
        t4 = exp_variants(pool, 12 if not a.quick else 8, seeds)
        t5, ws, xs, ys = exp_weights(pool, 12 if not a.quick else 8, seeds, [0.25, 0.5, 1, 2, 3, 5, 8, 12])
    p = Params()
    report = f"""# Experimental results

Generated by `run_experiments.py`. Default parameters: capacity={p.capacity}, tau={p.tau},
w_truck={p.w_truck}, w_delay={p.w_delay}, 4 destinations,
Poisson arrivals at 2 packages per tau, {seeds} random instances per size, node limit {LIMIT:,}.

`gap %` = (cost - reference) / reference; `best hit` = how often the algorithm matched the reference.

## 1. All algorithms, small instances
{t1}

## 2. Scalable algorithms, larger instances
{t2}

## 3. Heuristic strength (nodes expanded until optimal solution proven)
{t3}

![heuristics](heuristics_nodes.png)

## 4. Model variations (n = {12 if not a.quick else 8}, mean over instances)
{t4}

## 5. Weight sweep: trucks vs delivery time (n = {12 if not a.quick else 8})
{t5}

![tradeoff](weight_tradeoff.png)

![quality vs effort](quality_vs_effort.png)
"""
    with open(os.path.join(OUT, "RESULTS.md"), "w") as fh:
        fh.write(report)
    plots((hs, hser), (ws, xs, ys), rows_large)
    print(report)


if __name__ == "__main__":
    main()
