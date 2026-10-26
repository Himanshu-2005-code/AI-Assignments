# Rule checks for the Robo-Football environment (run: python -m unittest discover tests).
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from robofootball.game import (A, B, KICKOFF, TOTAL_TURNS, State, apply_move, kickoff_state,
                               legal_moves)


# Build a state with chosen positions for A's five pieces then B's five (A,B tuples of 5 cells).
def make(a, b, ball, to_move=A, turn=0, score=(0, 0)):
    return State(tuple(a) + tuple(b), ball, to_move, turn, score)


# Default quiet layout used by several tests.
A0 = ((2, 0), (1, 1), (1, 3), (0, 0), (0, 2))
B0 = ((4, 4), (4, 3), (3, 4), (5, 4), (5, 2))


class TestRules(unittest.TestCase):
    # Random games never put two pieces in one cell, never leave the board, keeper stays on goal line.
    def test_invariants_over_random_games(self):
        rnd = random.Random(0)
        for _ in range(50):
            s = kickoff_state()
            while not s.is_over():
                s = apply_move(s, rnd.choice(legal_moves(s)))
                self.assertEqual(len(set(s.pos)), 10)
                for r, c in s.pos:
                    self.assertTrue(0 <= r < 6 and 0 <= c < 5)
                self.assertEqual(s.pos[4][0], 0)
                self.assertEqual(s.pos[9][0], 5)

    # Turns alternate strictly, regardless of possession, and the match stops at the budget.
    def test_alternation_and_end(self):
        s = kickoff_state()
        for t in range(TOTAL_TURNS):
            self.assertEqual(s.to_move, t % 2)
            s = apply_move(s, legal_moves(s)[0])
        self.assertTrue(s.is_over())
        self.assertEqual(legal_moves(s), [])

    # Shooting is only offered in the two rows nearest the opponent's goal.
    def test_shoot_only_in_attacking_third(self):
        s = make(A0, B0, ball=0)                       # A carrier on row 2
        self.assertFalse(any(m[0] == "shoot" for m in legal_moves(s)))
        s = make(((4, 0),) + A0[1:], B0, ball=0)       # row 4 = attacking third for A
        self.assertTrue(any(m[0] == "shoot" for m in legal_moves(s)))
        s = make(A0, ((1, 4),) + B0[1:], ball=5, to_move=B)   # B carrier on row 1
        self.assertTrue(any(m[0] == "shoot" for m in legal_moves(s)))

    # Shot is a goal when keeper is 2+ columns away: score, reset to kickoff, conceder has ball.
    def test_goal_resets(self):
        s = make(((4, 0),) + A0[1:], ((4, 4), (4, 3), (3, 4), (5, 4), (5, 3)), ball=0)
        n = apply_move(s, ("shoot", 0))
        self.assertEqual(n.score, (1, 0))
        self.assertEqual(n.pos, KICKOFF)
        self.assertEqual(n.possession(), B)
        self.assertEqual(n.to_move, B)

    # Shot is saved when keeper is within one column: keeper gets ball, nothing else changes.
    def test_save(self):
        s = make(((4, 1),) + A0[1:], ((4, 4), (4, 3), (3, 4), (5, 4), (5, 2)), ball=0)
        n = apply_move(s, ("shoot", 0))
        self.assertEqual(n.score, (0, 0))
        self.assertEqual(n.ball, 9)
        self.assertEqual(n.pos, s.pos)

    # Dribbling next to an opponent (diagonal counts) hands them the ball.
    def test_tackle_after_dribble(self):
        s = make(A0, ((3, 2),) + B0[1:], ball=0)       # carrier (2,0); b0 at (3,2)
        n = apply_move(s, ("dribble", 0, (2, 1)))      # (2,1) is diagonal to (3,2)
        self.assertEqual(n.ball, 5)
        n2 = apply_move(s, ("dribble", 0, (3, 0)))     # (3,0) is 2 columns away from (3,2)
        self.assertEqual(n2.ball, 0)

    # With several adjacent opponents the lowest-index one wins the ball.
    def test_tackle_tiebreak(self):
        b = ((3, 2), (3, 1), (4, 3), (5, 4), (5, 2))
        s = make(A0, b, ball=0)
        n = apply_move(s, ("dribble", 0, (2, 1)))      # adjacent to b0 (3,2) and b1 (3,1)
        self.assertEqual(n.ball, 5)

    # A pass is blocked by an opponent on the line but not by one off the line; dribbles cannot overlap.
    def test_pass_blocking_and_no_overlap(self):
        s = make(((2, 0), (2, 4), (1, 3), (0, 0), (0, 2)), ((2, 2), (4, 3), (3, 4), (5, 4), (5, 2)), ball=0)
        passes = [m for m in legal_moves(s) if m[0] == "pass"]
        self.assertNotIn(("pass", 0, 1), passes)       # b0 stands on row 2 between them
        s2 = make(((2, 0), (2, 4), (1, 3), (0, 0), (0, 2)), ((3, 2), (4, 3), (3, 4), (5, 4), (5, 2)), ball=0)
        self.assertIn(("pass", 0, 1), [m for m in legal_moves(s2) if m[0] == "pass"])
        for m in legal_moves(s):
            if m[0] == "dribble":
                self.assertNotIn(m[2], s.pos)

    # Without the ball a team moves exactly one own piece; keeper only sideways on its goal line.
    def test_defensive_moves(self):
        s = make(A0, B0, ball=0, to_move=B)            # B does not have the ball
        moves = legal_moves(s)
        self.assertTrue(all(m[0] == "move" and m[1] >= 5 for m in moves))
        for m in moves:
            if m[1] == 9:
                self.assertEqual(m[2][0], 5)
        self.assertNotIn(("move", 9, (4, 2)), moves)

    # apply_move never mutates the old state (search relies on this).
    def test_apply_is_pure(self):
        s = kickoff_state()
        before = s.key()
        apply_move(s, legal_moves(s)[0])
        self.assertEqual(s.key(), before)


if __name__ == "__main__":
    unittest.main()
