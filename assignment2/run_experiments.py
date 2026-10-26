# Runs all Part-3 experiments and writes tables (results/*.md, results/*.json) and plots (results/*.png).
# Usage: python run_experiments.py [pruning|greedy|heuristics|depth|mcts|all]
import json
import os
import random
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from robofootball.agents import GreedyAgent, MCTSAgent, MinimaxAgent, RandomAgent
from robofootball.game import apply_move, kickoff_state, legal_moves, render
from robofootball.match import head_to_head, play_match

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
GAMES = 30      # games per pairing, sides alternate every game


# Save a markdown table.
def write_table(name, header, rows, note=""):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    text = "\n".join(lines) + ("\n\n" + note if note else "") + "\n"
    with open(os.path.join(OUT, name + ".md"), "w") as f:
        f.write(text)
    print(f"\n== {name} ==\n{text}")


# Result row for the first agent of a head-to-head: W/D/L, goals, shots, cost per move.
def summarize(r, games):
    return [f"{r['x_win']}/{r['draw']}/{r['y_win']}", f"{r['x_goals']}-{r['y_goals']}",
            f"{r['x_shots']}-{r['y_shots']}", f"{1000 * r['x_sec'] / max(r['x_moves'], 1):.1f}",
            f"{r['x_nodes'] / max(r['x_moves'], 1):.0f}"]


# Three board positions that are not the kickoff: a mid-game position, one just before a shot, one with the ball in B's half.
def test_positions():
    from robofootball.game import State
    rnd = random.Random(7)
    s = kickoff_state()
    for _ in range(14):                                   # position 1: after 14 random turns
        s = apply_move(s, rnd.choice(legal_moves(s)))
    p1 = s
    a = ((4, 0), (3, 3), (2, 1), (1, 3), (0, 2))          # position 2: A carrier on the left wing, B keeper centre
    b = ((5, 4), (4, 2), (3, 0), (3, 4), (5, 2))
    p2 = State(a + b, 0, 0, 20, (0, 0))
    a = ((1, 1), (2, 3), (2, 1), (1, 3), (0, 2))          # position 3: B has ball, A defending, open play
    b = ((2, 2), (3, 3), (3, 1), (4, 3), (5, 2))
    p3 = State(a + b, 5, 1, 30, (0, 0))
    return {"mid-game (random 14 turns)": p1, "A winger shot chance": p2, "B on the ball, A defending": p3}


# Experiment 1: minimax vs alpha-beta, same heuristic, depths 2-5, three non-kickoff positions.
def exp_pruning():
    rows, plot = [], {}
    for pname, pos in test_positions().items():
        for d in (2, 3, 4, 5):
            mm, ab = MinimaxAgent(d, "field", prune=False), MinimaxAgent(d, "field", prune=True)
            t = time.perf_counter(); m1 = mm.choose(pos); t_mm = time.perf_counter() - t
            t = time.perf_counter(); m2 = ab.choose(pos); t_ab = time.perf_counter() - t
            n_mm, n_ab = mm.stats["nodes"], ab.stats["nodes"]
            rows.append([pname, d, n_mm, n_ab, f"{100 * (1 - n_ab / n_mm):.1f}%", f"{t_mm:.3f}", f"{t_ab:.3f}",
                         "yes" if m1 == m2 else "NO"])
            plot.setdefault(pname, []).append((d, n_mm, n_ab))
    write_table("pruning", ["position", "depth", "nodes minimax", "nodes alpha-beta", "nodes saved", "sec minimax",
                            "sec alpha-beta", "same move"], rows,
                "Nodes = every state visited by the search (root included).")
    plt.figure(figsize=(6, 4))
    for pname, pts in plot.items():
        plt.plot([p[0] for p in pts], [p[1] for p in pts], "o--", label=f"minimax: {pname}")
        plt.plot([p[0] for p in pts], [p[2] for p in pts], "s-", label=f"alpha-beta: {pname}")
    plt.yscale("log"); plt.xlabel("search depth (plies)"); plt.ylabel("nodes visited")
    plt.legend(fontsize=6); plt.title("Pruning vs no pruning"); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "pruning.png"), dpi=130); plt.close()


# Experiment 2: greedy vs alpha-beta search (same heuristic), also each against random.
def exp_greedy():
    hdr = ["pairing (first agent listed first)", "W/D/L", "goals", "shots", "ms/move first", "nodes/move first"]
    rows = []
    for name, mx, my in [
        ("alpha-beta d3 field vs greedy field", lambda g: MinimaxAgent(3, "field"), lambda g: GreedyAgent("field")),
        ("alpha-beta d4 field vs greedy field", lambda g: MinimaxAgent(4, "field"), lambda g: GreedyAgent("field")),
        ("greedy field vs random", lambda g: GreedyAgent("field"), lambda g: RandomAgent(g)),
        ("alpha-beta d3 field vs random", lambda g: MinimaxAgent(3, "field"), lambda g: RandomAgent(g)),
    ]:
        rows.append([name] + summarize(head_to_head(mx, my, GAMES), GAMES))
    write_table("greedy_vs_search", hdr, rows, f"{GAMES} games per pairing, sides alternate, first 8 turns random.")


# Experiment 3: heuristic vs heuristic head to head, and each against common opponents.
def exp_heuristics():
    hdr = ["pairing (first agent listed first)", "W/D/L", "goals", "shots", "ms/move first", "nodes/move first"]
    rows = []
    for name, mx, my in [
        ("alpha-beta d3 field vs alpha-beta d3 structure", lambda g: MinimaxAgent(3, "field"), lambda g: MinimaxAgent(3, "structure")),
        ("alpha-beta d4 field vs alpha-beta d4 structure", lambda g: MinimaxAgent(4, "field"), lambda g: MinimaxAgent(4, "structure")),
        ("alpha-beta d4 field vs greedy structure", lambda g: MinimaxAgent(4, "field"), lambda g: GreedyAgent("structure")),
        ("alpha-beta d4 structure vs greedy structure", lambda g: MinimaxAgent(4, "structure"), lambda g: GreedyAgent("structure")),
        ("alpha-beta d4 field vs random", lambda g: MinimaxAgent(4, "field"), lambda g: RandomAgent(g)),
        ("alpha-beta d4 structure vs random", lambda g: MinimaxAgent(4, "structure"), lambda g: RandomAgent(g)),
    ]:
        rows.append([name] + summarize(head_to_head(mx, my, GAMES), GAMES))
    write_table("heuristics", hdr, rows, f"{GAMES} games per pairing, sides alternate, first 8 turns random.")


# Experiment 4: alpha-beta strength and cost as depth grows (opponents: random and greedy field).
def exp_depth():
    hdr = ["depth", "vs random W/D/L", "vs random goals", "vs greedy W/D/L", "vs greedy goals", "ms/move", "nodes/move"]
    rows, ms, wins = [], [], []
    depths = (1, 2, 3, 4, 5, 6)
    for d in depths:
        r1 = head_to_head(lambda g: MinimaxAgent(d, "field"), lambda g: RandomAgent(g), GAMES)
        r2 = head_to_head(lambda g: MinimaxAgent(d, "field"), lambda g: GreedyAgent("field"), GAMES)
        ms_d = 1000 * (r1["x_sec"] + r2["x_sec"]) / (r1["x_moves"] + r2["x_moves"])
        nodes_d = (r1["x_nodes"] + r2["x_nodes"]) / (r1["x_moves"] + r2["x_moves"])
        rows.append([d, f"{r1['x_win']}/{r1['draw']}/{r1['y_win']}", f"{r1['x_goals']}-{r1['y_goals']}",
                     f"{r2['x_win']}/{r2['draw']}/{r2['y_win']}", f"{r2['x_goals']}-{r2['y_goals']}",
                     f"{ms_d:.1f}", f"{nodes_d:.0f}"])
        ms.append(ms_d)
        wins.append(100 * (r1["x_win"] + r2["x_win"] + 0.5 * (r1["draw"] + r2["draw"])) / (2 * GAMES))
    write_table("depth", hdr, rows, "Alpha-beta with the field heuristic. Sides alternate, first 8 turns random.")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(depths, wins, "o-", color="tab:blue"); ax.set_xlabel("search depth (plies)")
    ax.set_ylabel("score % vs random+greedy (win=1, draw=0.5)", color="tab:blue")
    ax2 = ax.twinx(); ax2.plot(depths, ms, "s--", color="tab:red"); ax2.set_yscale("log")
    ax2.set_ylabel("ms per move", color="tab:red"); plt.title("Depth: strength vs cost"); fig.tight_layout()
    plt.savefig(os.path.join(OUT, "depth.png"), dpi=130); plt.close()


# Experiment 5: MCTS vs the other strategies, with growing iteration budgets.
def exp_mcts():
    hdr = ["pairing (first agent listed first)", "W/D/L", "goals", "shots", "ms/move first", "nodes/move first"]
    rows = []
    for name, mx, my in [
        ("mcts 100 it vs greedy structure", lambda g: MCTSAgent(100, seed=g), lambda g: GreedyAgent("structure")),
        ("mcts 300 it vs greedy structure", lambda g: MCTSAgent(300, seed=g), lambda g: GreedyAgent("structure")),
        ("mcts 1000 it vs greedy structure", lambda g: MCTSAgent(1000, seed=g), lambda g: GreedyAgent("structure")),
        ("mcts 300 it vs random", lambda g: MCTSAgent(300, seed=g), lambda g: RandomAgent(g)),
        ("mcts 300 it vs alpha-beta d3 field", lambda g: MCTSAgent(300, seed=g), lambda g: MinimaxAgent(3, "field")),
        ("mcts 1000 it vs alpha-beta d3 field", lambda g: MCTSAgent(1000, seed=g), lambda g: MinimaxAgent(3, "field")),
        ("alpha-beta d4 field vs greedy structure (reference)", lambda g: MinimaxAgent(4, "field"), lambda g: GreedyAgent("structure")),
    ]:
        rows.append([name] + summarize(head_to_head(mx, my, GAMES), GAMES))
    write_table("mcts", hdr, rows, f"{GAMES} games per pairing, sides alternate, MCTS roll-out depth 16.")


EXPERIMENTS = {"pruning": exp_pruning, "greedy": exp_greedy, "heuristics": exp_heuristics, "depth": exp_depth,
               "mcts": exp_mcts}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in EXPERIMENTS.items():
        if which in ("all", name):
            t0 = time.time()
            fn()
            print(f"[{name}] done in {time.time() - t0:.0f}s")
