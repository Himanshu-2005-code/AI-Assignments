# Assignment 1 — Learnings (one-page recall sheet)

**Problem in one line:** load arriving packages into identical trucks to minimise
`w_truck·#trucks + w_delay·avg delivery time`. A truck is a stack, so a package for a farther
stop can never be loaded behind one for a nearer stop — that trip simply can't take it.

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
5. **D**ispatch happens when the last package of the trip is in and the truck is back. Destination order is a **hard rule**, not a priced violation: `APPEND` simply isn't an available action if it would put a farther package behind a nearer one.

## Formulation (draw this on the board)

- **State** = (next package `i`, for each truck: `free_at` and the open trip's contents).
- **Actions** = `APPEND k` (add to truck k's trip) · `NEW k` (send truck k's trip, start a new one) · `TRUCK` (bring in another truck) · `FINISH`.
- **Cost** = `w_truck` per truck added, plus the trip's delays (scaled by `w_delay/n`) when it leaves. Path cost = objective.
- **Tricks:** dispatch is decided retroactively, so there is no "wait" action. Trucks are sorted, so identical trucks give no duplicate states.
- **Heuristic `h_open`** = driving time of unplaced packages + delay of open trips if they left now. It is admissible because adding packages only delays existing ones.
- **Ordering as a hard constraint:** rather than pricing a violation, `APPEND k` is only offered when the new package's destination is ≤ the destination of whoever's already at truck k's door. Local search (SA/GA) decodes arbitrary `(truck, brk)` encodings, so an encoding that would violate this is simply scored `+inf` and rejected by the ordinary accept/select logic — no separate validity checker needed.
- **Genetic algorithm encoding** = `truck[i]` (which truck carries package i) plus `brk[i]` (does package i start a new trip) — the same solution space the tree search explores, so costs compare directly against A*.

---

## Nine learnings (one sentence each)

1. **LIFO is patience sorting:** every trip is a non-increasing run of destinations by construction, so extra trucks act as extra sorting stacks.
2. **Two levers trade off:** more trucks, or more waiting (for a fuller or better-ordered trip). The weights decide which wins; ordering itself is a hard rule, not a lever.
3. **The heuristic decides scalability:** `h_open` cuts A*'s nodes by two to three orders of magnitude versus UCS at the same n.
4. **Uninformed search is hopeless:** all goals are at depth n, so BFS enumerates almost everything. DFS returns its first plan, tens of percent off.
5. **A heuristic blind to a cost term misleads greedy methods:** `h` ignores future trucks, so greedy best-first buys trucks (+100–140%). A* is safe because it keeps `g`.
6. **Local search is the fallback once the tree gets too big:** simulated annealing and the genetic algorithm both land within a few percent of the proven optimum at n≤12, using a fixed number of plan evaluations instead of an exploding search tree.
7. **The genetic algorithm needs enough population/generations to keep up as n grows:** pop=40/gen=200 is competitive with simulated annealing up to n=12, but falls behind at n=16 in a small sample — a fixed budget doesn't scale as well as SA's single long trajectory.
8. **A hard constraint is simpler than a priced one, and the assignment asks for exactly that:** `APPEND` just isn't offered for an out-of-order package — no rehandle-time parameter, no "how expensive is a violation" sweep, nothing to tune.
9. **Crossover + mutation over `(truck, brk)` works because it's the same space as the tree search:** a GA child is just another point in the plan space `evaluate()` already scores — an invalid one (violates ordering) simply scores `+inf`, so no separate decoder or checker is needed.

## Numbers worth quoting (quick-run sample, see `results/RESULTS.md` for the regenerated tables)

| Fact | Value |
|---|---|
| A* `h_open` vs UCS nodes, n = 8 | 74 vs 3,568 |
| Genetic algorithm gap to optimum, n = 8 / n = 16 | 0.0% / 20.0% |
| Simulated annealing gap to optimum, n = 8 / n = 16 | 0.0% / 1.3% |
| Value of a 2nd truck (fixed fleet of 1 vs free), n = 8 | average delay 8.57 → 4.17 |

## Likely questions, short answers

- **Why is `h_open` admissible?** Adding a package to a trip never makes earlier packages arrive sooner: the trip's dispatch only moves later from here. Packages not yet placed need at least their driving time.
- **Why is the ordering rule hard instead of priced?** The assignment says packages should be loaded respecting destination order "as far as possible" because they unload from the front — that's a statement about which loadings are physically possible, not an invitation to invent a penalty for the rest. Making it hard also keeps the model to exactly what's asked: no extra parameter, no extra cost term.
- **Why does the heuristic not bound trucks?** One truck could serve everything by waiting, so 0 extra trucks is the only safe lower bound.
- **Why not BFS?** Costs are not uniform per step and every goal is at the same depth, so BFS is neither optimal nor fast.
- **Why genetic algorithm *and* simulated annealing, if they do similar jobs?** They explore the same plan space differently — SA perturbs one candidate over time, GA keeps a population and recombines survivors — so comparing them shows that the result (a good plan without systematic search) doesn't depend on which local-search mechanism you pick.
- **How would you handle the online case?** Re-plan with A*, SA, or the GA every time window over the known packages (rolling horizon).
- **Real-life extensions?** Heterogeneous trucks (truck type in the state), road networks (route length instead of k·τ), deadlines (weighted delay or pruning), limited staging buffer (buffer in the state), and uncertain arrivals (MDP or expectimax).
