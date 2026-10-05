# Assignment 1 — Learnings (one-page recall sheet)

**Problem in one line:** load arriving packages into identical trucks to minimise
`w_truck·#trucks + w_delay·avg delivery time`. A truck is a stack, so a package loaded in
front of one for an earlier stop costs rehandling time.

---

## Recommended approach (remember: "A* small, SA/GA large")

| Situation | Use | Why |
|---|---|---|
| ≤ ~16–20 packages in the planning window | **A\* with `h_open`** | Optimal; expands 100–1000× fewer nodes than UCS |
| Larger windows, best plan quickly | **Simulated annealing** or **Genetic algorithm** | Both land within a few percent of the proven optimum at every size tested, at a small fixed cost (no search tree) |
| Arrivals not known in advance | **Rolling-horizon planning**, re-solving with A*/SA/GA each window | Only the known packages can be planned over |

Only algorithms the lectures actually taught are here: BFS/DFS (Aug 20), the g(n)-only
priority-queue search the course itself calls "Best-First Search" i.e. UCS (Aug 20), A* (Aug
25/27, Sep 1), Greedy best-first as the top-1 case of beam search (Sep 1), beam search (Sep 1),
simulated annealing (Sep 3), and the genetic algorithm (Sep 10).

## Assumptions it relies on (say "the AOLID five")

1. **A**rrivals are known for the planning window (offline problem).
2. **O**ne highway with equidistant stops: stop k is k·τ away, and a trip goes to its farthest stop and back.
3. **L**oad-on-arrival: a trip is loaded in arrival order, and the last package loaded is at the door (LIFO).
4. **I**dentical trucks with capacity C (default 4), all free at the start of the day.
5. **D**ispatch happens when the last package of the trip is in and the truck is back. An order violation costs a fixed rehandle time (0.5τ per blocking package).

## Formulation (draw this on the board)

- **State** = (next package `i`, for each truck: `free_at` and the open trip's contents).
- **Actions** = `APPEND k` (add to truck k's trip) · `NEW k` (send truck k's trip, start a new one) · `TRUCK` (bring in another truck) · `FINISH`.
- **Cost** = `w_truck` per truck added, plus the trip's delays (scaled by `w_delay/n`) when it leaves. Path cost = objective.
- **Tricks:** dispatch is decided retroactively, so there is no "wait" action. Trucks are sorted, so identical trucks give no duplicate states.
- **Heuristic `h_open`** = driving time of unplaced packages + delay of open trips if they left now. It is admissible because adding packages only delays existing ones.
- **Genetic algorithm encoding** = `truck[i]` (which truck carries package i) plus `brk[i]` (does package i start a new trip) — the same solution space the tree search explores, so costs compare directly against A*.

---

## Nine learnings (one sentence each)

1. **LIFO is patience sorting:** a trip with no rehandling is a non-increasing run of destinations, so extra trucks act as extra sorting stacks.
2. **Three levers trade off:** more trucks, more waiting, or more rehandling. The weights decide which wins.
3. **The heuristic decides scalability:** `h_open` cuts A*'s nodes by two to three orders of magnitude versus UCS at the same n.
4. **Uninformed search is hopeless:** all goals are at depth n, so BFS enumerates almost everything. DFS returns its first plan, tens of percent off.
5. **A heuristic blind to a cost term misleads greedy methods:** `h` ignores future trucks, so greedy best-first buys trucks (+100–140%). A* is safe because it keeps `g`.
6. **Local search is the fallback once the tree gets too big:** simulated annealing and the genetic algorithm both stay within a few percent of the proven optimum at every size tested, using a fixed number of plan evaluations instead of an exploding search tree.
7. **The genetic algorithm needs enough population/generations:** pop=40/gen=200 is competitive with simulated annealing; a much smaller population (e.g. 10) loses diversity and gives noticeably worse plans — the same failure mode as too narrow a beam.
8. **Order matters little when it is priced:** a staging area (any load order) gains only a little. With expensive rehandling, the optimiser simply avoids violations.
9. **Crossover + mutation over `(truck, brk)` works because it's the same space as the tree search:** a GA child is just another point in the plan space `evaluate()` already scores, so no separate decoder is needed.

## Numbers worth quoting (quick-run sample, see `results/RESULTS.md` for the regenerated tables)

| Fact | Value |
|---|---|
| A* `h_open` vs UCS nodes, n = 8 | about 77 vs about 8,800 |
| Genetic algorithm gap to optimum, n = 8 | about 0.4% |
| Simulated annealing gap to optimum, n = 8 | about 1.0% |
| Value of a 2nd truck (fleet of 1 vs free), n = 8 | average delay 6.6 → 4.5 |

## Likely questions, short answers

- **Why is `h_open` admissible?** Adding a package to a trip never makes earlier packages arrive sooner: dispatch moves later, and unloading or rehandling time only grows. Packages not yet placed need at least their driving time.
- **Why does the heuristic not bound trucks?** One truck could serve everything by waiting, so 0 extra trucks is the only safe lower bound.
- **Why not BFS?** Costs are not uniform per step and every goal is at the same depth, so BFS is neither optimal nor fast.
- **Why genetic algorithm *and* simulated annealing, if they do similar jobs?** They explore the same plan space differently — SA perturbs one candidate over time, GA keeps a population and recombines survivors — so comparing them shows that the result (a good plan without systematic search) doesn't depend on which local-search mechanism you pick.
- **How would you handle the online case?** Re-plan with A*, SA, or the GA every time window over the known packages (rolling horizon).
- **Real-life extensions?** Heterogeneous trucks (truck type in the state), road networks (route length instead of k·τ), deadlines (weighted delay or pruning), limited staging buffer (buffer in the state), and uncertain arrivals (MDP or expectimax).
