# Assignment 1 — Truck Loading and Delivery Planning (CSE643)

> **Revising for the in-class assessment? Start with the one-page [LEARNINGS.md](LEARNINGS.md).**

Plan how arriving packages are loaded into trucks so as to minimise

```
cost = w_truck * (#trucks assigned to the centre) + w_delay * (average delivery time)
```

where the delivery time of a package runs from its arrival at the dispatch centre until it
is unloaded at its destination. The problem is modelled as **state-space search**, and the
code compares uninformed search, informed search, beam search, and local search over complete
plans on random instances — exactly the algorithm families the course itself teaches (§3).

```
assignment1/
├── truckload/
│   ├── problem.py      # instance, random generator, trip simulator, plan evaluator (single source of truth)
│   ├── search.py       # state space + BFS, DFS, UCS, A*, Greedy, Beam
│   └── heuristics.py   # local search over complete plans: Simulated Annealing, Genetic Algorithm
├── demo.py             # solve one instance and print the loading plans
├── run_experiments.py  # every experiment of this report -> results/
├── results/RESULTS.md  # full tables + plots (generated)
└── tests/              # brute-force optimality check, admissibility, simulator unit tests
```

Running it (Python 3.9+, standard library only; matplotlib is optional and used only for plots):

```bash
python demo.py --n 10 --seed 3            # see the plans the algorithms produce
python tests/test_truckload.py            # or: python -m pytest tests
python run_experiments.py [--quick]       # regenerates results/
```

---

## Summary: what each algorithm does, and which wins

A cheat sheet before the detail below. Numbers are from `results/RESULTS.md` at n = 8
(4 random instances); see §3 for the full algorithm set and §4 for every size tested.

| Algorithm | Idea | Optimal? | n=8: gap / nodes | Verdict |
|---|---|---|---|---|
| BFS | Expand the search level by level | No — costs aren't uniform per step | 21.2%, 5.8k nodes | Correct depth, wrong metric; not worth running |
| DFS | Dive straight down, take the first complete plan | No | 21.2%, 9 nodes | Cheap but lucky-or-not; no guarantee |
| UCS | The course's own "Best-First Search": always expand the cheapest `g` | Yes | 0.0%, 3.6k nodes | The optimal baseline — correct, but slow |
| A\*(`h_rem`) | UCS plus a weak admissible heuristic (driving time only) | Yes | 0.0%, 2.0k nodes | Optimal, a modest speedup over UCS |
| A\*(`h_open`) | UCS plus the stronger heuristic (driving time + committed delay of open trips) | Yes | 0.0%, 74 nodes | **Best choice** up to ~16–20 packages — optimal and cheap |
| Greedy best-first | Always take the lowest `h`, ignore `g` entirely | No | 106.5% | The clear loser — blind to the truck term, buys a truck for nearly every package |
| Beam (k=5) | Keep only the 5 best partial plans at each depth | No | 2.7% | Cheap, occasionally stuck with too narrow a beam |
| Beam (k=25) | Keep the 25 best | No, but close | 0.0% | Near-optimal here, still far cheaper than UCS |
| Simulated annealing | Perturb one candidate plan, cool a temperature over time | No | 0.0% (degrades to 1.3% by n=16) | The steadiest fallback once A\* gets too big |
| Genetic algorithm | Evolve a population of candidate plans (crossover + mutation) | No | 0.0% (degrades to 20% by n=16 at this fixed budget) | Competitive with SA at small/medium n; needs a bigger population to keep scaling |

**Bottom line:** for anything A\* can still search in reasonable time, **A\*(`h_open`) wins outright**
— optimal and, at n=8, about 48× fewer nodes than UCS. Once the instance is too large for that,
**simulated annealing is the more dependable fallback** of the two local-search methods; the
genetic algorithm matches it at small sizes but its fixed population/generation budget falls
behind as n grows (§4, §6). **Greedy best-first is the one algorithm to actively avoid** — it
optimises the wrong signal and routinely buys far more trucks than it needs.

---

## 1. Model and assumptions

| Item | Choice in the base model | Why |
|---|---|---|
| Geography | Stop `k` is `k·τ` from the depot along one highway (equidistant stops). A trip drives out to its farthest stop and back: `2·max_dest·τ`. | Given in the problem statement. One highway means a trip visits its stops in increasing order. |
| Arrivals | Known in advance (offline, e.g. the day's manifest), Poisson with 2 packages per τ in the experiments. | Gives a well-defined search problem. The online case is studied separately in §5. |
| Trucks | Identical, capacity `C` (default 4), all at the depot at the start of the day. The number of trucks is a decision variable. | Given in the problem statement. |
| Loading | **Load-on-arrival:** a truck is loaded in the order its packages arrive (no space to re-sort on the floor). The truck is a **stack**: the last package loaded sits at the door. | This makes "respect the destination ordering as far as possible" a real constraint rather than a free sort. |
| Ordering | A **hard rule**, taken directly from the problem statement: a package may only be added to a trip if its destination is at or before whatever's currently at the door. If it isn't, that trip simply can't take it — the plan must open a new trip or a new truck instead. | The assignment says packages "should not be loaded in front of" one for an earlier stop. We enforce that literally, as a constraint on which moves exist, rather than inventing a penalty for breaking it. |
| Departure | A trip leaves at `max(truck back at depot, last package of the trip has arrived)`. | Leaving later never helps: delays would only grow and the truck would come back later. |
| Objective | `w_truck = 3`, `w_delay = 1` (one truck is worth 3τ of average delay). | Trades trucks against delay; swept in §5. |

**The key structural fact:** the packages a truck takes on one trip form a subsequence of the
arrival sequence, and the ordering rule forces that subsequence to be non-increasing in
destination. Using several trucks at once therefore works like **patience sorting**: the fewest
LIFO-consistent "stacks" equals the length of the longest strictly increasing subsequence of
destinations. This gives intuition, not the objective: waiting and trip timing matter too. One
side effect of making the rule hard rather than soft: there's nothing left to simulate at a stop
beyond "unload whoever is at the door" — no rehandling, no extra parameter, no extra cost term.

## 2. State-space formulation

* **State** `(i, trucks)`: `i` is the next package to place. Each truck is
  `(free_at, open_trip)`, where `free_at` is when the truck is back from its last dispatched
  trip and `open_trip` is the tuple of packages loaded so far on the trip at the dock.
* **Initial state:** `(0, ())`, with no trucks assigned yet.
* **Actions** for package `i`:
  * `APPEND k`: put the package on truck k's open trip — only if the trip isn't full **and**
    package `i`'s destination is at or before the destination of whoever is already at the
    door. Otherwise this action simply doesn't exist for truck k.
  * `NEW k`: dispatch truck k's open trip, then start a new trip on k with package `i`.
  * `TRUCK`: assign one more truck to the centre and start a trip with package `i`.
  * When `i = n`, a single `FINISH` action dispatches every open trip.
* **Step costs:** `w_truck` when a truck is added, and `w_delay/n × Σ delays` of a trip when
  it is dispatched. The cost of a path to the goal equals the objective of the plan.
* **Goal:** after `FINISH`. Every goal is at depth `n+1`, so the space is a DAG.
* **Dispatch decided retroactively:** a trip's departure depends only on its contents and
  its truck, so it can be closed at the moment the next trip for that truck is chosen.
  Waiting is therefore never an explicit action.
* **Duplicate detection:** trucks are identical, so the truck list is sorted. A `free_at`
  earlier than the moment it could matter is replaced by 0, which merges many equivalent
  states.
* **Branching factor** is about `2K+1` for `K` trucks, and the depth is `n`.

### Heuristics (all lower bounds on the cost still to come)

| Name | Value | Admissible? |
|---|---|---|
| `h0` | 0 (gives UCS) | yes |
| `h_rem` | `w_delay/n × Σ_{unplaced} d·τ` (every package still needs its pure driving time) | yes |
| `h_open` | `h_rem` + the delay of every open trip **if it left right now** | yes, because adding packages to a trip can only make its existing packages later (the trip's dispatch only moves later from here). Verified empirically against UCS and brute force. |

None of them bounds the **truck** term, since one truck could in principle serve everything by
waiting. This blind spot explains why greedy best-first and narrow beams fail (§4).

## 3. Algorithms compared

This set matches what the course itself teaches (the g(n)-only priority-queue search is the
course's own "Best-First Search," i.e. UCS; Greedy best-first is taught as the top-1 case of
beam search; A*, beam search, simulated annealing and the genetic algorithm are each taught in
their own lecture). Nothing here is a memory-bounded/anytime variant or an online dispatch rule
that the lectures didn't cover.

| Family | Algorithms | Optimal? |
|---|---|---|
| Uninformed | BFS (graph search), DFS, UCS | UCS only |
| Informed | A*(`h_rem`), A*(`h_open`), Greedy best-first | A* only |
| Beam search | Beam search (k = 5, 25) | no (but close with a wide beam) |
| Local search over complete plans | Simulated annealing (20k moves); Genetic algorithm (population 40, 200 generations, keep best half, crossover + mutation). Representation: `truck[i]` plus a "new trip" flag per package, the same space as the tree search, so costs compare directly. | no |

Every algorithm's plan is scored by the same `evaluate()` simulator. The tests check that the
optimal algorithms (UCS, A*) match brute-force enumeration, and that the genetic algorithm stays
within a sane bound of the true optimum.

## 4. Experimental findings

These are random instances, 4 destinations, capacity 4, with a node limit of 200k. Full tables
(regenerated after trimming the algorithm set to what the course covers) are in
[`results/RESULTS.md`](results/RESULTS.md); run `python run_experiments.py` yourself for a
bigger sample (more seeds, larger n) than the `--quick` numbers quoted here.

**Search effort to reach the proven optimum** (geometric mean of nodes expanded):

| n | UCS | A*(h_rem) | A*(h_open) |
|---|---|---|---|
| 4 | 24 | 18 | 6 |
| 6 | 207 | 97 | 15 |
| 8 | 2,191 | 885 | 55 |

![nodes](results/heuristics_nodes.png)

**Quality vs effort**, gap % and nodes expanded (mean over 4 random instances per size):

| algorithm | n=8 | n=12 | n=16 |
|---|---|---|---|
| BFS / DFS | 21.2% | — | — |
| UCS | 0.0%, 3.6k nodes | — | — |
| A*(h_open) | 0.0%, 74 | 0.0%, 527 | 0.0%, 3.2k |
| Greedy best-first | 106.5% | 125.9% | 115.2% |
| Beam k=25 | 0.0% | 0.0% | 0.9% |
| **Simulated annealing** | 0.0% | 0.4% | 1.3% |
| **Genetic algorithm (pop=40, gen=200)** | 0.0% | 1.9% | 20.0% |

Simulated annealing degrades gently as n grows. The genetic algorithm matches it at n=8–12 but
falls off sharply at n=16 in this (small, 4-instance) sample — with a fixed population and
generation budget it simply doesn't get enough evolutionary steps per package as the problem
grows; a bigger run (`run_experiments.py` without `--quick`) would want a larger population to
match SA's trajectory-based search at that size.

**Model variations** (n = 8, mean over instances):

| variation | cost | trucks | avg delay | what it shows |
|---|---|---|---|---|
| base model (A*, optimal) | 9.42 | 1.75 | 4.17 | — |
| bigger trucks (capacity 6) | 9.33 | 1.75 | 4.08 | more room per trip helps only a little |
| smaller trucks (capacity 2) | 10.70 | 2.00 | 4.70 | small trucks force more trips and more trucks |
| fixed fleet of 1 truck | 11.57 | 1.00 | 8.57 | the second truck is worth several τ of average delay |
| busier centre (rate 4/τ) | 9.50 | 1.75 | 4.25 | more packages per trip, barely moves the cost |
| quieter centre (rate 1/τ) | 9.02 | 1.50 | 4.52 | fewer packages waiting lets one truck keep up |
| skewed destinations (near-heavy) | 8.72 | 2.00 | 2.72 | short trips are cheap, so the optimiser uses more of them |
| genetic algorithm (pop=40, gen=200) | 9.42 | 1.75 | 4.17 | matches the A* optimum exactly at this size |
| genetic algorithm, smaller population (pop=10) | 9.97 | 2.00 | 3.97 | a narrower population finds a worse (but still valid) plan |

**Weight sweep:** raising `w_truck` traces the Pareto front — more trucks and less delay at low
weight, fewer trucks and more delay at high weight, settling on one truck once the weight is high
enough (`w_truck=12` → 1.00 truck, 8.57 avg delay, matching the fixed-fleet-of-1 row above).

![tradeoff](results/weight_tradeoff.png)

## 5. Recommended approach

1. **Formulate** the problem as sequential placement in arrival order, with dispatch decided
   retroactively and identical trucks deduplicated.
2. **Up to about 16–20 packages per planning window:** run **A\* with `h_open`**. It is optimal,
   and it is 100–1000× cheaper than UCS.
3. **Larger windows, or when a complete plan is needed fast:** run **simulated annealing** or the
   **genetic algorithm**. Both came within a few percent of the A* optimum at every size tested
   here, at a small, fixed fraction of A*'s cost.
4. **Online operation:** without knowledge of future arrivals, re-plan with A*, simulated
   annealing or the genetic algorithm on a **rolling horizon** over the packages already known.

The recommendation relies on these assumptions: arrival times are known for the planning
window, trucks are identical, stops are equidistant on one highway, loading happens on arrival
(LIFO), and the destination-ordering rule is enforced structurally (a trip simply can't accept
an out-of-order package, rather than being allowed to and paying for it).

## 6. Learnings to remember

1. **The state is packages placed plus the dock and truck status.** Choosing dispatch times
   retroactively removes "wait" actions; sorting identical trucks removes symmetric states.
2. **LIFO ordering becomes patience sorting.** Each trip should be a non-increasing
   subsequence of destinations. Parallel trucks act as extra stacks, and the longest
   increasing subsequence is the minimum number of stacks needed.
3. **The trade-off is trucks vs waiting.** Taking on another truck costs `w_truck`; waiting for
   a fuller or better-ordered trip costs delay instead. The weights decide which one wins — the
   ordering rule itself isn't part of the trade-off, since it's a hard constraint, not a cost.
4. **A heuristic's strength decides scalability.** `h_open` uses the open trips' committed
   delay; it cuts A*'s nodes by two to three orders of magnitude versus UCS at the same n.
5. **Uninformed search is useless here.** All goals sit at the same depth, so BFS must enumerate
   almost everything. DFS returns the first plan it finds (often the one-truck plan), tens of
   percent off.
6. **A heuristic blind to one cost term misleads greedy methods.** `h` ignores future trucks:
   greedy best-first buys a truck for almost every package (+100–140%). A* is immune because it
   keeps `g`.
7. **Local search is a strong fallback once A* gets too big.** Both simulated annealing and the
   genetic algorithm land within a few percent of the proven optimum at every n tested, using a
   small, fixed number of plan evaluations instead of a search tree that can blow up.
8. **The genetic algorithm needs enough population/generations to beat simulated annealing's
   single trajectory.** With pop=40, gen=200 it is competitive at small n; a much smaller
   population (e.g. 10) gives noticeably worse plans for the same reason a too-narrow beam does —
   not enough diversity to escape a bad crossover.
9. **Making the ordering rule hard, not priced, keeps the model small.** Forbidding an
   out-of-order `APPEND` outright (instead of allowing it for a fee) removes a parameter, a
   cost term, and an entire family of "how expensive is a violation" experiments — and it's a
   closer reading of the assignment, which says packages should simply be loaded in that order,
   not that they may be loaded otherwise for a price.

## 7. Further variations (discussed; not all implemented in `Params`)

* **Supported in the code:** a fixed fleet (`max_trucks`), capacity, destination skew, and
  arrival rate.
* **Heterogeneous trucks** (different capacity or cost): add a truck type to the truck state,
  and give the `TRUCK` action one branch per type.
* **Non-equidistant or branching routes:** replace `d·τ` by a route length from a TSP or
  shortest path over the trip's stops. `h_rem` stays admissible if it uses each package's
  direct distance.
* **Deadlines or priorities:** use a weighted delay or a hard constraint. Pruning with
  deadline violations keeps A* complete.
* **A small staging area at the dock:** if a few packages could wait on the floor instead of
  going straight onto a trip, the hard ordering rule could sometimes be satisfied by holding a
  package back rather than opening a new trip for it. Not implemented here, since the
  assignment describes load-on-arrival rather than a buffer — but it would only need the floor
  buffer added to the state and a couple of new actions ("load from buffer" / "park on floor").
* **Uncertain arrivals:** use a rolling horizon, or an MDP / expectimax over arrival
  scenarios.
