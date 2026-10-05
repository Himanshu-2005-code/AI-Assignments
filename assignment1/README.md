# Assignment 1 — Truck Loading and Delivery Planning (CSE643)

> **Revising for the in-class assessment? Start with the one-page [LEARNINGS.md](LEARNINGS.md).**

Plan how arriving packages are loaded into trucks so as to minimise

```
cost = w_truck * (#trucks assigned to the centre) + w_delay * (average delivery time)
```

where the delivery time of a package runs from its arrival at the dispatch centre until it
is unloaded at its destination. The problem is modelled as **state-space search**, and the
code compares uninformed search, informed search, memory-bounded and anytime search, local
search, and online dispatch rules on random instances.

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

## 1. Model and assumptions

| Item | Choice in the base model | Why |
|---|---|---|
| Geography | Stop `k` is `k·τ` from the depot along one highway (equidistant stops). A trip drives out to its farthest stop and back: `2·max_dest·τ`. | Given in the problem statement. One highway means a trip visits its stops in increasing order. |
| Arrivals | Known in advance (offline, e.g. the day's manifest), Poisson with 2 packages per τ in the experiments. | Gives a well-defined search problem. The online case is studied separately in §5. |
| Trucks | Identical, capacity `C` (default 4), all at the depot at the start of the day. The number of trucks is a decision variable. | Given in the problem statement. |
| Loading | **Load-on-arrival:** a truck is loaded in the order its packages arrive (no space to re-sort on the floor). The truck is a **stack**: the last package loaded sits at the door. | This makes "respect the destination ordering as far as possible" a real constraint rather than a free sort. |
| Ordering violations | Allowed but costly. At each stop, every package in front of the deepest package for that stop is taken out and put back, costing `rehandle` time (0.5τ) each and delaying everyone after it. | A soft constraint is more realistic than forbidding violations outright, and the optimiser can trade it against waiting or extra trucks. |
| Departure | A trip leaves at `max(truck back at depot, last package of the trip has arrived)`. | Leaving later never helps: delays would only grow and the truck would come back later. |
| Objective | `w_truck = 3`, `w_delay = 1` (one truck is worth 3τ of average delay). | Trades trucks against delay; swept in §5. |

**The key structural fact:** the packages a truck takes on one trip form a subsequence of the
arrival sequence, and that trip needs no rehandling exactly when the subsequence is
non-increasing in destination. Using several trucks at once therefore works like **patience
sorting**: the fewest LIFO-consistent "stacks" equals the length of the longest strictly
increasing subsequence of destinations. This gives intuition, not the objective: waiting and
trip timing matter too.

## 2. State-space formulation

* **State** `(i, trucks)`: `i` is the next package to place. Each truck is
  `(free_at, open_trip)`, where `free_at` is when the truck is back from its last dispatched
  trip and `open_trip` is the tuple of packages loaded so far on the trip at the dock.
* **Initial state:** `(0, ())`, with no trucks assigned yet.
* **Actions** for package `i`:
  * `APPEND k`: put the package on truck k's open trip, if it is not full.
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
| `h_open` | `h_rem` + the delay of every open trip **if it left right now** | yes, because adding packages to a trip can only make its existing packages later (dispatch moves later, plus extra unloading or rehandling). Verified empirically against UCS and brute force. |

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
| 4 | 36 | 27 | 6 |
| 6 | 458 | 191 | 18 |
| 8 | 6,476 | 1,994 | 60 |

![nodes](results/heuristics_nodes.png)

**Quality vs effort**, mean gap % and mean nodes expanded:

| algorithm | n=8 | n=12 | n=16 |
|---|---|---|---|
| BFS / DFS | 22.0% | — | — |
| UCS | 0%, 8.8k nodes | — | — |
| A*(h_open) | 0%, 77 | 0%, 1.1k | 0%, 17k |
| Greedy best-first | 118% | 132% | 116% |
| Beam k=25 | 0.1% | 0.2% | 4.2% |
| **Simulated annealing** | 1.0% | 4.7% | 2.2% |
| **Genetic algorithm (pop=40, gen=200)** | 0.4% | 4.2% | 9.4% |

The genetic algorithm tracks simulated annealing closely at small n and both degrade gently as n
grows, since neither does systematic search — they're the two "when A* gets too big" fallbacks.

**Model variations** (n = 8, mean over instances):

| variation | cost | trucks | avg delay | what it shows |
|---|---|---|---|---|
| base model (A*, optimal) | 8.97 | 1.50 | 4.47 | — |
| staging area (free load order) | 8.69 | 1.50 | 4.19 | the LIFO constraint costs little when planned well |
| rehandling 2τ instead of 0.5τ | 9.36 | 1.75 | 4.11 | the optimiser avoids violations and uses more trips instead |
| capacity 2 / 6 | 10.70 / 8.65 | 2.00 / 1.25 | 4.70 / 4.90 | small trucks hurt; large ones help less than you'd expect |
| fixed fleet of 1 truck | 9.57 | 1.00 | 6.57 | the second truck is worth a few τ of average delay |
| genetic algorithm (pop=40, gen=200) | 9.01 | 1.50 | 4.51 | within about 0.4% of the A* optimum at this size |

**Weight sweep:** raising `w_truck` traces the Pareto front — more trucks and less delay at low
weight, fewer trucks and more delay at high weight, with the optimiser settling on one truck once
the weight is high enough.

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
(LIFO), and a violation is a fixed time cost.

## 6. Learnings to remember

1. **The state is packages placed plus the dock and truck status.** Choosing dispatch times
   retroactively removes "wait" actions; sorting identical trucks removes symmetric states.
2. **LIFO ordering becomes patience sorting.** Each trip should be a non-increasing
   subsequence of destinations. Parallel trucks act as extra stacks, and the longest
   increasing subsequence is the minimum number of stacks needed.
3. **The trade-off is trucks vs waiting vs rehandling.** Each lever substitutes for the others,
   and the weights decide which one wins.
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
9. **Let rehandling be priced.** With cheap rehandling the optimum accepts some violations;
   with expensive rehandling it re-routes packages instead. A staging area gains only a little
   over smart load-on-arrival.

## 7. Further variations (discussed; partly supported by flags in `Params`)

* **Supported in the code:** a fixed fleet (`max_trucks`), a staging area (`free_order`),
  unload and rehandle times, capacity, destination skew, and arrival rate.
* **Heterogeneous trucks** (different capacity or cost): add a truck type to the truck state,
  and give the `TRUCK` action one branch per type.
* **Non-equidistant or branching routes:** replace `d·τ` by a route length from a TSP or
  shortest path over the trip's stops. `h_rem` stays admissible if it uses each package's
  direct distance.
* **Deadlines or priorities:** use a weighted delay or a hard constraint. Pruning with
  deadline violations keeps A* complete.
* **Staging area of limited size `B`:** add the floor buffer to the state; actions become
  "load from buffer" or "park on floor". This interpolates between load-on-arrival and free
  order.
* **Uncertain arrivals:** use a rolling horizon, or an MDP / expectimax over arrival
  scenarios.
