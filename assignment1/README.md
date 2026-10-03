# Assignment 1 — Truck Loading and Delivery Planning (CSE643)

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
│   ├── search.py       # state space + BFS, DFS, UCS, A*, WA*, Greedy, IDA*, DFBnB, Beam
│   └── heuristics.py   # online dispatch rules, hill climbing, simulated annealing
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

| Family | Algorithms | Optimal? |
|---|---|---|
| Uninformed | BFS (graph search), DFS, UCS | UCS only |
| Informed | A*(`h_rem`), A*(`h_open`), Weighted A* (w = 1.5, 3), Greedy best-first | A* only; WA* is at most w× optimal |
| Memory-bounded / anytime | IDA*, depth-first branch-and-bound (DFBnB), beam search (k = 5, 25) | IDA* and DFBnB |
| Local search over complete plans | Steepest hill climbing with 5 random restarts, simulated annealing (20k moves). Representation: `truck[i]` plus a "new trip" flag per package, the same space as the tree search, so costs compare directly. | no |
| Rules (no search) | **Online** dispatcher (timeout, patience-sorting placement, waits for a returning truck if it is close, knobs tuned per instance); **Immediate** dispatch (every package leaves alone) | no |

Every algorithm's plan is scored by the same `evaluate()` simulator. The tests check that the
optimal algorithms match brute-force enumeration.

## 4. Experimental findings

These are 10 random instances per size, 4 destinations, capacity 4, with a node limit of 200k.
Full tables are in [`results/RESULTS.md`](results/RESULTS.md). The gap is measured against the
optimum, or against the best plan found when A* hit the limit (n = 30, and 3 instances at n = 20).

**Search effort to reach the proven optimum** (geometric mean of nodes expanded):

| n | UCS | A*(h_rem) | A*(h_open) | DFBnB(h_open) |
|---|---|---|---|---|
| 6 | 426 | 252 | 19 | 24 |
| 8 | 6,849 | 2,625 | 72 | 110 |
| 10 | hits limit | 30,758 | 258 | 509 |
| 14 | hits limit | hits limit | 3,066 | 7,061 |

![nodes](results/heuristics_nodes.png)

**Quality vs effort**, mean gap % and mean nodes expanded (or plans evaluated):

| algorithm | n=10 | n=16 | n=30 |
|---|---|---|---|
| BFS / DFS | not finished / 32% | — | — |
| UCS | 0%, 105k nodes | — | — |
| A*(h_open) | 0%, 303 | 0%, 17k | not finished |
| IDA*(h_open) | 0%, 11k | — | — |
| DFBnB(h_open) | 0%, 573 | 0%, 36k | 38% at limit |
| WA* w=1.5 | 2.2%, 198 | 1.7%, 5.9k | finished 1/10 |
| WA* w=3 | 6.1%, 68 | 7.5%, 473 | 4.2%, finished 7/10 |
| Beam k=25 | 0.4% | 20% | 101% |
| Greedy best-first | 116% | 117% | 139% |
| Hill climbing (5 restarts) | 2.3% | 3.6% | 8.7% |
| **Simulated annealing** | 1.2% | 1.4% | **0.6%** (best at n=30) |
| Online rule (tuned) | — | 17.6% | 17.5% |
| Immediate dispatch | 171% | 206% | 221% |

**Model variations** (n = 12, optimal plans):

| variation | cost | trucks | avg delay | what it shows |
|---|---|---|---|---|
| base model | 9.63 | 1.9 | 3.93 | — |
| staging area (free load order) | 9.39 | 1.9 | 3.69 | the LIFO constraint costs only about 2.5% when planned well |
| rehandling 2τ instead of 0.5τ | 9.82 | 2.0 | 3.82 | the optimiser stops violating the order (rehandles 0.8 → 0.1) and uses more trips instead |
| capacity 2 / 6 | 11.46 / 9.33 | 2.0 / 1.8 | 5.46 / 3.93 | small trucks hurt a lot; large ones help less |
| fixed fleet of 1 truck | 12.19 | 1 | 9.19 | the second truck is worth about 5τ of average delay |
| online naive rule (new truck when none idle) | 16.91 | 4.4 | 3.71 | myopic rules over-buy trucks |
| online rule, tuned | 11.26 | 2.0 | 5.25 | knowing future arrivals is worth about 17% |

**Weight sweep:** raising `w_truck` traces the Pareto front. There are 3.3 trucks at a delay of
2.8 when w = 0.25, and one truck at a delay of 9.2 from w = 8 upward. The jump from 2 trucks
to 1 is abrupt.

![tradeoff](results/weight_tradeoff.png)

## 5. Recommended approach

1. **Formulate** the problem as sequential placement in arrival order, with dispatch decided
   retroactively and identical trucks deduplicated.
2. **Up to about 16–20 packages per planning window:** run **A\* with `h_open`**. It is optimal,
   and it is 100–1000× cheaper than UCS. If memory is tight, use DFBnB, which is also optimal
   and costs about 2× the nodes with linear memory.
3. **Larger windows:** run **Weighted A\* (w ≈ 1.5–3)** when a quality bound is needed, or
   **simulated annealing** warm-started from the online rule. Simulated annealing came within
   1–2% of the best plan found at every size tested.
4. **Online operation:** run the planner on a **rolling horizon** over the packages already
   known, and fall back to the tuned online rule (patience-sorting placement, timeout, wait for
   a returning truck if it is close).

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
   delay; it cut A*'s nodes from 30k to 258 at n=10 and pushed the optimal limit from n≈10 to
   n≈20.
5. **Uninformed search is useless here.** All goals sit at the same depth, so BFS must enumerate
   almost everything (it timed out at n=10). DFS returns the first plan it finds (the one-truck
   plan), 13–32% off.
6. **A heuristic blind to one cost term misleads greedy methods.** `h` ignores future trucks:
   greedy best-first adds a truck for almost every package (+115–140%), and narrow beams bet on one truck and
   then drown in delay (beam gap rises with n). A* is immune because it keeps `g`.
7. **WA* is a cheap knob.** w = 3 gave about 6% worse plans for 5–40× fewer nodes, and it still
   finished most n=30 instances where A* did not.
8. **IDA* suffers on real-valued costs.** Nearly every f-value is distinct, so it repeats many
   iterations (36× A*'s nodes at n=10). DFBnB is the better linear-memory option.
9. **Local search wins at scale.** Simulated annealing came within about 1–2% everywhere and was
   the best at n=30. Hill climbing gets stuck because merging trucks is a large move.
10. **Information is worth about 17%.** A tuned online rule is about 17% above the offline
    optimum, and a naive rule that buys a truck whenever none is idle is 75% above it.
11. **Let rehandling be priced.** With cheap rehandling the optimum accepts some violations;
    with expensive rehandling it re-routes packages instead. A staging area gains only about
    2.5% over smart load-on-arrival.

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
  scenarios. The online rule above is the zero-lookahead end of that spectrum.
