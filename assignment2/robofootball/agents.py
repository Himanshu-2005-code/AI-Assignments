# Agents. Every agent has choose(state) -> move and a `stats` dict with the nodes it searched.
import random

from .game import apply_move, legal_moves
from .heuristics import HEURISTICS
from .mcts import mcts_move
from .search import INF, alphabeta, minimax


# Baseline: uniformly random legal move.
class RandomAgent:
    def __init__(self, seed=0):
        self.name = "random"
        self.rnd = random.Random(seed)
        self.stats = {"nodes": 0}

    def choose(self, state):
        return self.rnd.choice(legal_moves(state))


# No lookahead: play the move whose resulting position the heuristic likes best.
class GreedyAgent:
    def __init__(self, heuristic="field"):
        self.name = f"greedy-{heuristic}"
        self.h = HEURISTICS[heuristic]
        self.stats = {"nodes": 0}

    def choose(self, state):
        me = state.to_move
        best, best_move = -INF, None
        for move in legal_moves(state):
            self.stats["nodes"] += 1
            value = self.h(apply_move(state, move), me)
            if value > best:
                best, best_move = value, move
        return best_move


# Depth-limited minimax, with or without alpha-beta pruning. Picks the first best move at the root.
class MinimaxAgent:
    def __init__(self, depth=3, heuristic="field", prune=True):
        self.name = f"{'alphabeta' if prune else 'minimax'}-d{depth}-{heuristic}"
        self.depth, self.prune = depth, prune
        self.h = HEURISTICS[heuristic]
        self.stats = {"nodes": 0}

    def choose(self, state):
        me = state.to_move
        alpha, best, best_move = -INF, -INF, None
        for move in legal_moves(state):
            child = apply_move(state, move)
            if self.prune:
                value = alphabeta(child, self.depth - 1, alpha, INF, me, self.h, self.stats)
                alpha = max(alpha, value)
            else:
                value = minimax(child, self.depth - 1, me, self.h, self.stats)
            if value > best:
                best, best_move = value, move
        self.stats["nodes"] += 1        # the root itself
        return best_move


# MCTS with a fixed number of iterations and depth-limited random roll-outs.
class MCTSAgent:
    def __init__(self, iterations=300, rollout_depth=16, heuristic="field", seed=0):
        self.name = f"mcts-{iterations}it-r{rollout_depth}"
        self.iterations, self.rollout_depth = iterations, rollout_depth
        self.h = HEURISTICS[heuristic]
        self.rnd = random.Random(seed)
        self.stats = {"nodes": 0}

    def choose(self, state):
        return mcts_move(state, self.iterations, self.rollout_depth, self.h, self.rnd, stats=self.stats)
