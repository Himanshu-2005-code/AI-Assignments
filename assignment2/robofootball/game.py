# Robo-Football game environment: state, legal moves, applying a move, end of match.
# Two agents only ever talk to this file through State, legal_moves() and apply_move().
from __future__ import annotations

ROWS, COLS = 6, 5
TOTAL_TURNS = 80            # whole-match budget (40 turns per team), see README for why
A, B = 0, 1                 # team ids; A defends row 0 and attacks row 5, B the opposite
KEEPER = 4                  # index of the goalkeeper inside a team's list of 5 pieces
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# Kickoff formation for team A as (row, col) for pieces 0..3 (outfield) and 4 (keeper).
# Team B gets the mirror image (row -> 5 - row), so the two sides are symmetric.
KICKOFF_A = ((2, 1), (2, 3), (1, 1), (1, 3), (0, 2))


# Mirror a team-A position into team B's half of the board.
def mirror(pos):
    return (ROWS - 1 - pos[0], pos[1])


KICKOFF = KICKOFF_A + tuple(mirror(p) for p in KICKOFF_A)


# Team that owns piece index i (0-4 are A, 5-9 are B).
def team_of(i):
    return i // 5


# True if piece i is a goalkeeper.
def is_keeper(i):
    return i % 5 == KEEPER


# Row of a team's own goal line and of the line it attacks.
def goal_row(team):
    return 0 if team == A else ROWS - 1


# True if row r lies in the attacking third (two rows nearest the opponent's goal) of the team.
def in_attacking_third(team, r):
    return r >= ROWS - 2 if team == A else r <= 1


# Immutable snapshot of the match. Nothing mutates it; apply_move builds a new one.
class State:
    __slots__ = ("pos", "ball", "to_move", "turn", "score")

    def __init__(self, pos, ball, to_move, turn, score):
        self.pos = pos            # tuple of 10 (row, col): pieces 0-4 are A, 5-9 are B
        self.ball = ball          # index of the piece holding the ball
        self.to_move = to_move    # team whose turn it is (A or B)
        self.turn = turn          # number of turns already played
        self.score = score        # (goals of A, goals of B)

    # Team that currently has the ball.
    def possession(self):
        return team_of(self.ball)

    # True once the turn budget is used up.
    def is_over(self):
        return self.turn >= TOTAL_TURNS

    # Winner team id, or None for a draw (only meaningful when the match is over).
    def winner(self):
        if self.score[0] == self.score[1]:
            return None
        return A if self.score[0] > self.score[1] else B

    # Hashable key so states can be compared or cached.
    def key(self):
        return (self.pos, self.ball, self.to_move, self.turn, self.score)


# State at the start of the match, or after a goal: kickoff formation, conceding team has the ball.
def kickoff_state(ball_team=A, to_move=A, turn=0, score=(0, 0)):
    return State(KICKOFF, ball_team * 5, to_move, turn, score)


# Cells occupied by any piece, for emptiness checks.
def occupied(state):
    return set(state.pos)


# Moves for the team that does not have the ball: shift one own piece by one cell.
def _defensive_moves(state):
    team = state.to_move
    taken = occupied(state)
    moves = []
    for i in range(team * 5, team * 5 + 5):
        r, c = state.pos[i]
        steps = [(0, -1), (0, 1)] if is_keeper(i) else DIRS     # keeper: sideways only
        for dr, dc in steps:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in taken:
                moves.append(("move", i, (nr, nc)))
    return moves


# True if a pass from a to b is impossible: not a straight line, or an opponent stands between.
def pass_blocked(state, team, a, b):
    dr, dc = b[0] - a[0], b[1] - a[1]
    if not (dr == 0 or dc == 0 or abs(dr) == abs(dc)):
        return True                                             # not a legal pass line
    n = max(abs(dr), abs(dc))
    sr, sc = (dr > 0) - (dr < 0), (dc > 0) - (dc < 0)
    enemies = set(state.pos[(1 - team) * 5:(1 - team) * 5 + 5])
    for k in range(1, n):
        if (a[0] + sr * k, a[1] + sc * k) in enemies:
            return True
    return False


# Moves for the team that has the ball: shoot, pass, dribble (in this fixed order).
def _ball_moves(state):
    team = state.to_move
    i = state.ball
    r, c = state.pos[i]
    moves = []
    if in_attacking_third(team, r):
        moves.append(("shoot", i))
    for j in range(team * 5, team * 5 + 5):
        if j != i and not pass_blocked(state, team, (r, c), state.pos[j]):
            moves.append(("pass", i, j))
    taken = occupied(state)
    steps = [(0, -1), (0, 1)] if is_keeper(i) else DIRS         # keeper carrier: sideways only
    for dr, dc in steps:
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in taken:
            moves.append(("dribble", i, (nr, nc)))
    return moves


# All legal moves for the team to move. If none exist the team must skip its turn.
def legal_moves(state):
    if state.is_over():
        return []
    if state.possession() == state.to_move:
        moves = _ball_moves(state)
    else:
        moves = _defensive_moves(state)
    return moves or [("skip",)]


# Opposing piece that wins the ball after a dribble to cell, or None. Tie-break: lowest index.
def _tackler(pos, team, cell):
    for j in range((1 - team) * 5, (1 - team) * 5 + 5):
        if max(abs(pos[j][0] - cell[0]), abs(pos[j][1] - cell[1])) == 1:
            return j
    return None


# Build the next state after the team to move plays `move` (assumes the move is legal).
def apply_move(state, move):
    team = state.to_move
    nxt_turn = state.turn + 1
    nxt_team = 1 - team
    kind = move[0]
    pos, ball, score = state.pos, state.ball, state.score

    if kind == "move":
        _, i, cell = move
        pos = pos[:i] + (cell,) + pos[i + 1:]
    elif kind == "dribble":
        _, i, cell = move
        pos = pos[:i] + (cell,) + pos[i + 1:]
        tackler = _tackler(pos, team, cell)
        if tackler is not None:
            ball = tackler                                      # adjacent opponent wins the ball
    elif kind == "pass":
        ball = move[2]
    elif kind == "shoot":
        enemy_keeper = (1 - team) * 5 + KEEPER
        shooter_col = pos[move[1]][1]
        if abs(pos[enemy_keeper][1] - shooter_col) <= 1:
            ball = enemy_keeper                                 # saved: keeper takes the ball
        else:                                                   # goal: reset, conceding team kicks off
            score = (score[0] + 1, score[1]) if team == A else (score[0], score[1] + 1)
            return State(KICKOFF, (1 - team) * 5, nxt_team, nxt_turn, score)
    # kind == "skip": nothing changes except whose turn it is
    return State(pos, ball, nxt_team, nxt_turn, score)


# Text picture of the board: A pieces are a0-a3/aK, B pieces b0-b3/bK, '*' marks the ball holder.
def render(state):
    grid = {}
    for i, p in enumerate(state.pos):
        name = ("a" if team_of(i) == A else "b") + ("K" if is_keeper(i) else str(i % 5))
        grid[p] = name + ("*" if i == state.ball else " ")
    lines = []
    for r in range(ROWS - 1, -1, -1):                           # row 5 printed at the top
        cells = [grid.get((r, c), " . ") for c in range(COLS)]
        lines.append(f"{r} | " + " ".join(f"{x:3}" for x in cells))
    lines.append("    " + " ".join(f"{c:3}" for c in range(COLS)))
    lines.append(f"turn {state.turn}/{TOTAL_TURNS}  score A {state.score[0]} - B {state.score[1]}  "
                 f"to move: {'AB'[state.to_move]}  ball: {'AB'[state.possession()]}")
    return "\n".join(lines)
