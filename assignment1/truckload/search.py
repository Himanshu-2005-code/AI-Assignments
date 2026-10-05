"""State-space formulation and the search algorithms.

State  : (i, trucks) where ``i`` is the next package to place and each truck is
         (free_at, open_trip). ``free_at`` is when the truck is back from its
         last dispatched trip; ``open_trip`` is the tuple of packages loaded so
         far (in load order) on the trip currently at the dock.
Actions: for package i
           APPEND k  - load it on truck k's open trip (if not full)
           NEW k     - dispatch truck k's open trip (if any), start a new trip
                       on truck k with package i
           TRUCK     - bring in an additional truck, start a trip with i
         When i == n a single FINISH action dispatches every open trip.
Cost   : w_truck when a truck is added, w_delay/n * (sum of delays) of a trip
         when it is dispatched. Path cost of a goal = objective of the plan.

A trip departs at max(truck back, last package of the trip arrived), so
"dispatch" can be decided retroactively (offline problem, arrivals known).

Duplicate detection: trucks are identical, so the truck list is sorted; a
``free_at`` that is no later than the moment it can matter is replaced by 0.

Algorithms here are the ones covered in lecture (BFS/DFS, the g(n)-only
priority-queue search the course calls "Best-First Search" (= UCS), A*,
Greedy best-first as the top-1 case of beam search, and beam search itself).
"""
from __future__ import annotations

import heapq
import itertools
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .problem import Instance, Trip, trip_delay_sum

INF = float("inf")


class Node:
    __slots__ = ("i", "trucks", "done", "g", "parent", "closed", "key", "depth")

    def __init__(self, i, trucks, done, g, parent, closed, key):
        self.i = i
        self.trucks = trucks    # tuple of (free_at, open_ids, truck_id)
        self.done = done
        self.g = g
        self.parent = parent
        self.closed = closed    # list of Trip dispatched by the action into this node
        self.key = key
        self.depth = 0 if parent is None else parent.depth + 1


@dataclass
class SearchResult:
    algorithm: str
    plan: Optional[List[Trip]]
    cost: float
    expanded: int
    generated: int
    seconds: float
    status: str  # "ok" | "limit"

    @property
    def solved(self) -> bool:
        return self.plan is not None


class TruckLoadingProblem:
    def __init__(self, inst: Instance):
        self.inst = inst
        self.p = inst.params
        self.n = inst.n
        self.arr = [pk.arrival for pk in inst.packages]
        self.dest = [pk.dest for pk in inst.packages]
        self.coef = self.p.w_delay / self.n
        # suffix sums for the "remaining packages" part of the heuristics
        self.rem = [0.0] * (self.n + 1)
        for j in range(self.n - 1, -1, -1):
            self.rem[j] = self.rem[j + 1] + self.dest[j] * self.p.tau + self.p.unload
        self._open_cache: Dict[Tuple, float] = {}

    # -- state helpers ----------------------------------------------------
    def make_key(self, i, trucks, done):
        if done:
            return ("done",)
        nxt = self.arr[i] if i < self.n else INF
        sig = []
        for free, ids, _ in trucks:
            thr = self.arr[ids[-1]] if ids else nxt
            sig.append((free if free > thr else 0.0, ids))
        sig.sort()
        return (i, tuple(sig))

    def initial(self) -> Node:
        return Node(0, (), False, 0.0, None, [], self.make_key(0, (), False))

    def dispatch(self, free, ids):
        depart = max(free, self.arr[ids[-1]])
        s, ret, _ = trip_delay_sum(self.inst, ids, depart)
        return self.coef * s, ret

    def successors(self, node: Node) -> List[Node]:
        out = []
        if node.done:
            return out
        i, trucks = node.i, node.trucks
        if i == self.n:  # FINISH
            cost, closed = 0.0, []
            for free, ids, tid in trucks:
                if ids:
                    c, _ = self.dispatch(free, ids)
                    cost += c
                    closed.append(Trip(tid, ids))
            out.append(Node(i, trucks, True, node.g + cost, node, closed, ("done",)))
            return out
        seen = set()

        def push(new_trucks, step, closed):
            key = self.make_key(i + 1, new_trucks, False)
            if key in seen:
                return
            seen.add(key)
            out.append(Node(i + 1, new_trucks, False, node.g + step, node, closed, key))

        for k, (free, ids, tid) in enumerate(trucks):
            if ids and len(ids) < self.p.capacity:  # APPEND k
                push(trucks[:k] + ((free, ids + (i,), tid),) + trucks[k + 1:], 0.0, [])
            if ids:  # NEW k (dispatch the open trip first)
                c, ret = self.dispatch(free, ids)
                push(trucks[:k] + ((ret, (i,), tid),) + trucks[k + 1:], c, [Trip(tid, ids)])
            else:    # idle truck takes the package
                push(trucks[:k] + ((free, (i,), tid),) + trucks[k + 1:], 0.0, [])
        if self.p.max_trucks is None or len(trucks) < self.p.max_trucks:  # TRUCK
            push(trucks + ((0.0, (i,), len(trucks)),), self.p.w_truck, [])
        return out

    # -- heuristics ---------------------------------------------------------
    def h_zero(self, node: Node) -> float:
        return 0.0

    def h_remaining(self, node: Node) -> float:
        """Every unplaced package needs at least its pure driving time."""
        return 0.0 if node.done else self.coef * self.rem[node.i]

    def h_open(self, node: Node) -> float:
        """h_remaining + delay of every open trip if it left right now. Adding
        packages to a trip can only delay the ones already in it, so this is
        still a lower bound (admissible)."""
        if node.done:
            return 0.0
        h = self.coef * self.rem[node.i]
        for free, ids, _ in node.trucks:
            if ids:
                ck = (free if free > self.arr[ids[-1]] else 0.0, ids)
                v = self._open_cache.get(ck)
                if v is None:
                    v = self.dispatch(free, ids)[0]
                    self._open_cache[ck] = v
                h += v
        return h

    def plan_of(self, node: Node) -> List[Trip]:
        trips = []
        while node is not None:
            trips.extend(node.closed)
            node = node.parent
        # order per truck: by first package (trips on one truck never interleave)
        trips.sort(key=lambda t: t.ids[0])
        return trips


HEURISTICS = {"h0": "h_zero", "h_rem": "h_remaining", "h_open": "h_open"}


def _result(name, prob, goal, expanded, generated, t0, status="ok"):
    plan = prob.plan_of(goal) if goal is not None else None
    return SearchResult(name, plan, goal.g if goal else INF, expanded, generated,
                        time.perf_counter() - t0, status)


# --------------------------------------------------------------------------
# Uninformed tree/graph searches (BFS, DFS)
# --------------------------------------------------------------------------
def bfs(prob: TruckLoadingProblem, node_limit: int = 10**6) -> SearchResult:
    t0 = time.perf_counter()
    start = prob.initial()
    frontier = deque([start])
    seen = {start.key}
    expanded = generated = 0
    while frontier:
        node = frontier.popleft()
        expanded += 1
        if expanded > node_limit:
            return _result("BFS", prob, None, expanded, generated, t0, "limit")
        for ch in prob.successors(node):
            generated += 1
            if ch.done:  # goal test on generation
                return _result("BFS", prob, ch, expanded, generated, t0)
            if ch.key not in seen:
                seen.add(ch.key)
                frontier.append(ch)
    return _result("BFS", prob, None, expanded, generated, t0, "fail")


def dfs(prob: TruckLoadingProblem, node_limit: int = 10**6) -> SearchResult:
    t0 = time.perf_counter()
    stack = [prob.initial()]
    seen = set()
    expanded = generated = 0
    while stack:
        node = stack.pop()
        if node.done:
            return _result("DFS", prob, node, expanded, generated, t0)
        if node.key in seen:
            continue
        seen.add(node.key)
        expanded += 1
        if expanded > node_limit:
            return _result("DFS", prob, None, expanded, generated, t0, "limit")
        children = prob.successors(node)
        generated += len(children)
        stack.extend(reversed(children))  # first action (APPEND) explored first
    return _result("DFS", prob, None, expanded, generated, t0, "fail")


# --------------------------------------------------------------------------
# Best-first family: UCS (= the g(n)-only priority-queue search taught as
# "Best-First Search" on Aug 20), A*, and Greedy best-first (the top-1 case
# of beam search, Sep 1).
# --------------------------------------------------------------------------
def best_first(prob: TruckLoadingProblem, name: str, h: Callable[[Node], float],
               wg: float = 1.0, wh: float = 1.0, node_limit: int = 10**6) -> SearchResult:
    t0 = time.perf_counter()
    start = prob.initial()
    tie = itertools.count()
    frontier = [(wh * h(start), next(tie), start)]
    best_g = {start.key: 0.0}
    expanded = generated = 0
    while frontier:
        _, _, node = heapq.heappop(frontier)
        if node.g > best_g.get(node.key, INF) + 1e-12:
            continue  # stale entry
        if node.done:
            return _result(name, prob, node, expanded, generated, t0)
        expanded += 1
        if expanded > node_limit:
            return _result(name, prob, None, expanded, generated, t0, "limit")
        for ch in prob.successors(node):
            generated += 1
            if ch.g < best_g.get(ch.key, INF) - 1e-12:
                best_g[ch.key] = ch.g
                heapq.heappush(frontier, (wg * ch.g + wh * h(ch), next(tie), ch))
    return _result(name, prob, None, expanded, generated, t0, "fail")


def ucs(prob, **kw):
    return best_first(prob, "UCS", prob.h_zero, **kw)


def astar(prob, heuristic="h_open", **kw):
    return best_first(prob, f"A*({heuristic})", getattr(prob, HEURISTICS[heuristic]), **kw)


def greedy(prob, heuristic="h_open", **kw):
    return best_first(prob, "Greedy-BeFS", getattr(prob, HEURISTICS[heuristic]), wg=0.0, **kw)


def beam_search(prob, width=10, heuristic="h_open") -> SearchResult:
    """Layered beam search: every action places exactly one package, so all
    nodes in a layer are comparable. Keep the ``width`` best by g+h."""
    t0 = time.perf_counter()
    h = getattr(prob, HEURISTICS[heuristic])
    layer = [prob.initial()]
    expanded = generated = 0
    while True:
        if all(n.done for n in layer):
            goal = min(layer, key=lambda n: n.g)
            return _result(f"Beam(k={width})", prob, goal, expanded, generated, t0)
        nxt: Dict = {}
        for node in layer:
            expanded += 1
            for ch in prob.successors(node):
                generated += 1
                if ch.key not in nxt or ch.g < nxt[ch.key].g:
                    nxt[ch.key] = ch
        layer = sorted(nxt.values(), key=lambda c: c.g + h(c))[:width]
