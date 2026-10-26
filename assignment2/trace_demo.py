# Prints an alpha-beta trace on a real position (depth 2) so you can practise reading one by hand.
# Each line: indent = depth, move tried, alpha/beta when entering, and CUT where a branch is pruned.
from robofootball.game import State, apply_move, legal_moves
from robofootball.heuristics import h_field
from robofootball.search import INF

# A carrier on the left wing in the attacking third, B keeper in the centre.
A_POS = ((4, 0), (3, 3), (2, 1), (1, 3), (0, 2))
B_POS = ((5, 4), (4, 2), (3, 0), (3, 4), (5, 2))
START = State(A_POS + B_POS, 0, 0, 20, (0, 0))
ME = 0


# Alpha-beta that prints every step; returns the node value.
def trace(state, depth, alpha, beta, move_name, indent):
    pad = "  " * indent
    if depth == 0:
        v = h_field(state, ME)
        print(f"{pad}{move_name:<28} leaf value = {v}")
        return v
    maximizing = state.to_move == ME
    print(f"{pad}{move_name:<28} {'MAX' if maximizing else 'MIN'}  alpha={alpha} beta={beta}")
    best = -INF if maximizing else INF
    moves = legal_moves(state)
    for k, mv in enumerate(moves):
        v = trace(apply_move(state, mv), depth - 1, alpha, beta, str(mv), indent + 1)
        if maximizing:
            best = max(best, v); alpha = max(alpha, best)
        else:
            best = min(best, v); beta = min(beta, best)
        if alpha >= beta:
            rest = len(moves) - k - 1
            if rest:
                print(f"{pad}  CUT: alpha={alpha} >= beta={beta}, skipping {rest} remaining move(s)")
            break
    print(f"{pad}{'':<28} returns {best}")
    return best


if __name__ == "__main__":
    trace(START, 2, -INF, INF, "root (A to move)", 0)
