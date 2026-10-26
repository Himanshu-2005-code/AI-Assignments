# Play full matches between two agents and run round-robin style tournaments.
import random
import time

from .game import A, B, apply_move, kickoff_state, legal_moves

OPENING_RANDOM_TURNS = 8    # first turns are random (seeded) so deterministic agents do not repeat one game


# Play one match. agent_a controls team A, agent_b team B. Returns result dict.
def play_match(agent_a, agent_b, seed=0, record=False):
    rnd = random.Random(seed)
    agents = (agent_a, agent_b)
    for ag in agents:
        ag.stats["nodes"] = 0
    secs = [0.0, 0.0]
    moves_made = [0, 0]
    shots = [0, 0]
    state = kickoff_state()
    history = [state] if record else None
    while not state.is_over():
        team = state.to_move
        if state.turn < OPENING_RANDOM_TURNS:
            move = rnd.choice(legal_moves(state))
        else:
            t0 = time.perf_counter()
            move = agents[team].choose(state)
            secs[team] += time.perf_counter() - t0
            moves_made[team] += 1
        if move[0] == "shoot":
            shots[team] += 1
        state = apply_move(state, move)
        if record:
            history.append(state)
    return {"score": state.score, "winner": state.winner(), "secs": secs, "moves": moves_made,
            "nodes": [agents[0].stats["nodes"], agents[1].stats["nodes"]], "shots": shots, "history": history}


# Play `games` matches between two agent factories, swapping sides every game.
# Returns wins/draws/losses and goals for the first agent, plus its average seconds per move.
def head_to_head(make_x, make_y, games=20, seed0=0):
    res = {"x_win": 0, "draw": 0, "y_win": 0, "x_goals": 0, "y_goals": 0, "x_sec": 0.0, "x_moves": 0,
           "y_sec": 0.0, "y_moves": 0, "x_nodes": 0, "y_nodes": 0, "x_shots": 0, "y_shots": 0}
    for g in range(games):
        x, y = make_x(g), make_y(g)
        x_is_a = g % 2 == 0
        r = play_match(x, y, seed=seed0 + g) if x_is_a else play_match(y, x, seed=seed0 + g)
        xi, yi = (0, 1) if x_is_a else (1, 0)
        res["x_goals"] += r["score"][xi]
        res["y_goals"] += r["score"][yi]
        res["x_sec"] += r["secs"][xi]
        res["x_moves"] += r["moves"][xi]
        res["x_nodes"] += r["nodes"][xi]
        res["y_nodes"] += r["nodes"][yi]
        res["x_shots"] += r["shots"][xi]
        res["y_shots"] += r["shots"][yi]
        res["y_sec"] += r["secs"][yi]
        res["y_moves"] += r["moves"][yi]
        if r["winner"] is None:
            res["draw"] += 1
        elif r["winner"] == (A if x_is_a else B):
            res["x_win"] += 1
        else:
            res["y_win"] += 1
    return res
