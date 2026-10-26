# Two evaluation functions. Each returns a number where higher is better for team `me`.
# h_field cares about WHERE the ball is; h_structure cares about passing options and defence.
from .game import A, KEEPER, ROWS, in_attacking_third, pass_blocked, team_of

GOAL_VALUE = 1000       # a goal is worth far more than any positional feature


# How many rows the piece at row r has advanced from its team's own goal line (0..5).
def _progress(team, r):
    return r if team == A else ROWS - 1 - r


# True if a shot from the carrier of `team` would be a goal right now (keeper 2+ columns away).
def _open_shot(state, team):
    i = state.ball
    r, c = state.pos[i]
    if not in_attacking_third(team, r):
        return False
    return abs(state.pos[(1 - team) * 5 + KEEPER][1] - c) > 1


# Field position: goals, possession, how far the ball has advanced, and shots on goal.
def h_field(state, me):
    opp = 1 - me
    score = GOAL_VALUE * (state.score[me] - state.score[opp])
    holder = state.possession()
    carrier_row = state.pos[state.ball][0]
    if holder == me:
        score += 60 + 15 * _progress(me, carrier_row)
        if in_attacking_third(me, carrier_row):
            score += 80 + (120 if _open_shot(state, me) else 0)
    else:
        score -= 60 + 15 * _progress(opp, carrier_row)
        if in_attacking_third(opp, carrier_row):
            score -= 80 + (120 if _open_shot(state, opp) else 0)
    # outfield pieces that have moved up the pitch give more attacking options
    mine = sum(_progress(me, state.pos[i][0]) for i in range(me * 5, me * 5 + 4))
    theirs = sum(_progress(opp, state.pos[i][0]) for i in range(opp * 5, opp * 5 + 4))
    return score + 3 * (mine - theirs)


# Chebyshev distance (king moves) between two cells.
def _dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# Structure: goals, possession, safe passes, supporting teammates, pressure, and keeper cover.
def h_structure(state, me):
    opp = 1 - me
    score = GOAL_VALUE * (state.score[me] - state.score[opp])
    holder = state.possession()
    cpos = state.pos[state.ball]
    if holder == me:
        score += 40
        # each unblocked pass is an escape route for the carrier
        for j in range(me * 5, me * 5 + 5):
            if j != state.ball and not pass_blocked(state, me, cpos, state.pos[j]):
                score += 12
        # teammates within two cells support the carrier
        score += 10 * sum(1 for j in range(me * 5, me * 5 + 4)
                          if j != state.ball and _dist(state.pos[j], cpos) <= 2)
        # opponents within one cell threaten a tackle after the next dribble
        score -= 15 * sum(1 for j in range(opp * 5, opp * 5 + 4) if _dist(state.pos[j], cpos) <= 2)
        if _open_shot(state, me):
            score += 150
    else:
        score -= 40
        # pressure: our pieces near their carrier
        score += 15 * sum(1 for j in range(me * 5, me * 5 + 4) if _dist(state.pos[j], cpos) <= 2)
        # keeper cover: staying within one column of their carrier turns shots into saves
        keeper_col = state.pos[me * 5 + KEEPER][1]
        score += 40 if abs(keeper_col - cpos[1]) <= 1 else -40
        if _open_shot(state, opp):
            score -= 150
    return score


HEURISTICS = {"field": h_field, "structure": h_structure}
