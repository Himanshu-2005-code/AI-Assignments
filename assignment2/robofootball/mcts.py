# Monte-Carlo tree search (UCT) with depth-limited random roll-outs.
import math
import random

from .game import A, apply_move, legal_moves


# One node of the search tree. `mover` is the team that played the move leading into this node.
class Node:
    __slots__ = ("state", "parent", "move", "mover", "children", "untried", "n", "w")

    def __init__(self, state, parent=None, move=None, mover=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.mover = mover
        self.children = []
        self.untried = legal_moves(state)
        self.n = 0          # visits
        self.w = 0.0        # sum of rewards from the point of view of `mover`


# UCT choice among fully expanded children: exploit (w/n) plus explore (sqrt(ln N / n)).
def _select_child(node, c):
    log_n = math.log(node.n)
    return max(node.children, key=lambda ch: ch.w / ch.n + c * math.sqrt(log_n / ch.n))


# Play random legal moves from `state` for up to `depth` plies, then score the end position.
def _rollout(state, depth, h, rnd, scale):
    for _ in range(depth):
        if state.is_over():
            break
        state = apply_move(state, rnd.choice(legal_moves(state)))
    return math.tanh(h(state, A) / scale)     # value in (-1, 1) from team A's point of view


# Run `iterations` rounds of select, expand, roll-out, back-up; return the most visited root move.
def mcts_move(root_state, iterations, rollout_depth, h, rnd, c=1.2, scale=300.0, stats=None):
    root = Node(root_state)
    for _ in range(iterations):
        node = root
        while not node.untried and node.children and not node.state.is_over():     # 1. select
            node = _select_child(node, c)
        if node.untried and not node.state.is_over():                              # 2. expand
            move = node.untried.pop(rnd.randrange(len(node.untried)))
            child = Node(apply_move(node.state, move), node, move, node.state.to_move)
            node.children.append(child)
            node = child
        value_a = _rollout(node.state, rollout_depth, h, rnd, scale)               # 3. roll-out
        while node is not None:                                                    # 4. back up
            node.n += 1
            if node.mover is not None:
                node.w += value_a if node.mover == A else -value_a
            node = node.parent
    if stats is not None:
        stats["nodes"] += sum(1 for _ in _walk(root))
    return max(root.children, key=lambda ch: ch.n).move


# Iterate over all nodes in a tree (only used to count tree size).
def _walk(node):
    yield node
    for ch in node.children:
        yield from _walk(ch)
