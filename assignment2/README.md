# Assignment 2: Robo-Football

Turn-based 6x5 football with adversarial-search agents. Pure Python, no dependencies except matplotlib for plots.

```
python -m unittest discover tests     # rule checks
python demo.py                        # one match, board printed every 8 turns
python trace_demo.py                  # printed alpha-beta trace on a real position
python run_experiments.py [pruning|greedy|heuristics|depth|mcts|all]
```

## Layout

| File | What it holds |
|---|---|
| `robofootball/game.py` | State, legal moves, apply move, end of match, board printing |
| `robofootball/heuristics.py` | `h_field` and `h_structure` |
| `robofootball/search.py` | Minimax and alpha-beta |
| `robofootball/mcts.py` | UCT Monte-Carlo tree search |
| `robofootball/agents.py` | Random, Greedy, Minimax/Alpha-beta, MCTS agents |
| `robofootball/match.py` | Match runner and side-alternating tournaments |
| `run_experiments.py` | All Part 3 experiments |

## Design decisions (where the spec left room)

- **Formation** (A shown, B is the mirror `row -> 5 - row`): outfield at (2,1), (2,3), (1,1), (1,3), keeper at (0,2). A kicks off with piece 0.
- **Turn budget: 80** (40 turns each). Random games score about 0.3 goals, so 80 turns gives a few scoring chances without making search experiments slow.
- **Tackle tie-break:** if several opponents are adjacent after a dribble, the one with the lowest piece index wins the ball.
- **Keeper with the ball** may pass or dribble sideways only (the sideways rule applies whenever the keeper moves).
- **No legal move:** the team skips its turn (`("skip",)`). This almost never happens.
- **Passing** targets any teammate (keeper included) on a straight line with no opponent strictly between.
- **Kickoff after a goal:** conceding team gets the ball at its piece 0, and the turn order keeps alternating.
- **Tournaments:** the first 8 turns are random (seeded), because two deterministic agents would otherwise replay the same game every time. Sides alternate every game.
- **Depth** counts plies, so depth 3 is me, opponent, me.
- **Nodes** = every state the search visits, root included, counted the same way for minimax and alpha-beta. For greedy it is the number of moves evaluated.

## Heuristics (higher is better for the team being scored)

Both start with `1000 * goal difference`, so a goal always dominates.

- **`h_field` (where is the ball):** possession (+/-60), ball-carrier progress (+/-15 per row advanced), a chance bonus when the carrier is in the attacking third (+80, and +120 more if the enemy keeper is 2+ columns away, i.e. a shot would score), plus 3 per row of advancement of the outfield pieces.
- **`h_structure` (passing and defence):** possession (+/-40), +12 per unblocked pass option, +10 per supporting teammate within 2 cells, -15 per opponent within 2 cells of my carrier, and when defending +15 per own piece pressing the enemy carrier, +/-40 for keeper cover (within one column of the enemy carrier), and -150 if the enemy has an open shot.

## Key rule facts that explain the results

1. Only a **dribble** can lose the ball (an opponent ends up adjacent). Passing is always safe, so a team with the ball can hold it forever by passing.
2. The team **without** the ball is the only one that can reposition pieces freely, so the attacking side cannot reposition while it holds the ball.
3. A shot scores only if the enemy keeper is 2+ columns away. The keeper moves one column per defensive turn, and a pass can switch the carrier's column by up to 4, so a goal needs a pass or dribble into the attacking third at a column the keeper cannot cover in one move.
4. Two sensible defenders therefore tend to draw 0-0.

## Results (30 games per pairing, sides alternate; W/D/L is from the first agent's view)

### 1. Pruning vs no pruning (field heuristic, three non-kickoff positions)
See `results/pruning.md` and `results/pruning.png`. Alpha-beta returned the same move as minimax in every case and visited 58-95% fewer nodes. The saving grows with depth.

### 2. Greedy vs search (`results/greedy_vs_search.md`)
Alpha-beta d3 vs greedy: 2/28/0. Alpha-beta d4 vs greedy: 13/17/0. Both beat random heavily (greedy 21/9/0, alpha-beta d3 20/10/0).

### 3. Heuristic vs heuristic (`results/heuristics.md`)
Same depth, field vs structure: 0/30/0 at depth 3 and at depth 4, but field took 38 shots to structure's 2 at depth 4. Against the same opponents, field wins more: vs random 25/5/0 against 11/19/0 for structure; vs greedy structure 4/26/0 against 1/29/0.

### 4. Depth vs performance (`results/depth.md`, `results/depth.png`)
Against greedy: depths 2 and 3 only draw (2/28/0), depth 4 and 5 win 13 of 30, depth 6 wins 17 of 30. Cost per move: 0.2 ms at depth 2, 4 ms at depth 4, 86 ms at depth 6 (about 3-4x per extra ply with pruning).

### 5. MCTS (`results/mcts.md`)
MCTS beats random (27/3/0 at 300 iterations) and beats greedy structure from 300 iterations up, but loses to alpha-beta d3 even with 1000 iterations (0/21/9) while costing 30-100x more time per move (37-125 ms against 1.1 ms).
