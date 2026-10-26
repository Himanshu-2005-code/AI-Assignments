# Depth-limited minimax and minimax with alpha-beta pruning.
# Both return the value of a state from the point of view of team `me` (the agent that is thinking).
# `stats["nodes"]` counts every state the search visits, so the two can be compared fairly.
from .game import apply_move, legal_moves

INF = float("inf")


# Plain minimax: me maximises, the opponent minimises, evaluate with h at depth 0 or match end.
def minimax(state, depth, me, h, stats):
    stats["nodes"] += 1
    if depth == 0 or state.is_over():
        return h(state, me)
    maximizing = state.to_move == me
    best = -INF if maximizing else INF
    for move in legal_moves(state):
        value = minimax(apply_move(state, move), depth - 1, me, h, stats)
        best = max(best, value) if maximizing else min(best, value)
    return best


# Same search with alpha-beta: stop looking at a node once it cannot change the final decision.
def alphabeta(state, depth, alpha, beta, me, h, stats):
    stats["nodes"] += 1
    if depth == 0 or state.is_over():
        return h(state, me)
    if state.to_move == me:
        best = -INF
        for move in legal_moves(state):
            best = max(best, alphabeta(apply_move(state, move), depth - 1, alpha, beta, me, h, stats))
            alpha = max(alpha, best)
            if alpha >= beta:        # MIN above already has a better option, so cut off
                break
        return best
    best = INF
    for move in legal_moves(state):
        best = min(best, alphabeta(apply_move(state, move), depth - 1, alpha, beta, me, h, stats))
        beta = min(beta, best)
        if alpha >= beta:            # MAX above already has a better option, so cut off
            break
    return best
