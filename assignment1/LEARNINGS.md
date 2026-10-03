# Assignment 1 — Learnings (one-page recall sheet)

**Problem in one line:** load arriving packages into identical trucks to minimise
`w_truck·#trucks + w_delay·avg delivery time`. A truck is a stack, so a package loaded in
front of one for an earlier stop costs rehandling time.

---

## Recommended approach (remember: "A* small, SA large, rule online")

| Situation | Use | Why |
|---|---|---|
| ≤ ~16–20 packages in the planning window | **A\* with `h_open`** | Optimal; expands 100–1000× fewer nodes than UCS |
| Memory is tight | **DFBnB with `h_open`** | Also optimal, linear memory, about 2× A*'s nodes |
| Larger windows, quality bound needed | **Weighted A\* (w = 1.5–3)** | Within w× of optimal; about 6% worse for 5–40× less work |
| Larger windows, best plan quickly | **Simulated annealing** | Within 1–2% of the best known at every size; best at n = 30 |
| Arrivals not known in advance | **Rolling-horizon planning plus the tuned online rule** | The rule is about 17% above the offline optimum |

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

---

## Ten learnings (one sentence each)

1. **LIFO is patience sorting:** a trip with no rehandling is a non-increasing run of destinations, so extra trucks act as extra sorting stacks.
2. **Three levers trade off:** more trucks, more waiting, or more rehandling. The weights decide which wins.
3. **The heuristic decides scalability:** `h_open` cut nodes from 30,758 to 258 at n = 10 and moved the optimal limit from n≈10 to n≈20.
4. **Uninformed search is hopeless:** all goals are at depth n, so BFS enumerates everything (it timed out at n = 10). DFS returns its first plan, 13–32% off.
5. **A heuristic blind to a cost term misleads greedy methods:** `h` ignores future trucks, so greedy best-first buys trucks (+115–140%) and narrow beams bet on one truck. A* is safe because it keeps `g`.
6. **WA* is a cheap quality-for-speed knob:** w = 3 finished most n = 30 instances, where A* did not.
7. **IDA* is bad with real-valued costs:** almost every f-value is distinct, so it repeats many iterations (36× A*'s nodes at n = 10). Prefer DFBnB.
8. **Local search wins at scale:** simulated annealing was within about 1% at n = 30. Hill climbing gets stuck because merging two trucks is a large move.
9. **Knowing future arrivals is worth about 17%:** that's the gap between the tuned online rule and the offline optimum. A naive "new truck when none is idle" rule is 75% worse.
10. **Order matters little when it is priced:** a staging area (any load order) gains only 2.5%. With expensive rehandling, the optimiser simply avoids violations.

## Numbers worth quoting

| Fact | Value |
|---|---|
| A* `h_open` vs UCS nodes, n = 10 | about 300 vs about 100,000 |
| Largest n solved optimally (200k-node limit) | about 20 |
| Value of a 2nd truck (fleet of 1 vs free) | average delay 9.2 → 3.9 (≈5τ) |
| Small trucks (C = 2) | cost +19% |
| Truck weight sweep | w = 0.25 gives 3.3 trucks, delay 2.8; w ≥ 8 gives 1 truck, delay 9.2 |

## Likely questions, short answers

- **Why is `h_open` admissible?** Adding a package to a trip never makes earlier packages arrive sooner: dispatch moves later, and unloading or rehandling time only grows. Packages not yet placed need at least their driving time.
- **Why does the heuristic not bound trucks?** One truck could serve everything by waiting, so 0 extra trucks is the only safe lower bound.
- **Why not BFS?** Costs are not uniform per step and every goal is at the same depth, so BFS is neither optimal nor fast.
- **How would you handle the online case?** Re-plan with A* or SA every time window over the known packages (rolling horizon), and use the tuned rule between re-plans.
- **Real-life extensions?** Heterogeneous trucks (truck type in the state), road networks (route length instead of k·τ), deadlines (weighted delay or pruning), limited staging buffer (buffer in the state), and uncertain arrivals (MDP or expectimax).
