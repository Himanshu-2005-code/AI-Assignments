| pairing (first agent listed first) | W/D/L | goals | shots | ms/move first | nodes/move first |
|---|---|---|---|---|---|
| mcts 100 it vs greedy structure | 2/21/7 | 2-7 | 2-11 | 12.7 | 100 |
| mcts 300 it vs greedy structure | 6/22/2 | 6-2 | 7-2 | 37.3 | 294 |
| mcts 1000 it vs greedy structure | 7/21/2 | 7-2 | 16-3 | 125.7 | 970 |
| mcts 300 it vs random | 27/3/0 | 33-0 | 35-10 | 37.8 | 294 |
| mcts 300 it vs alpha-beta d3 field | 0/17/13 | 0-17 | 1-42 | 37.2 | 294 |
| mcts 1000 it vs alpha-beta d3 field | 0/21/9 | 0-13 | 3-39 | 122.9 | 969 |
| alpha-beta d4 field vs greedy structure (reference) | 4/26/0 | 4-0 | 6-0 | 4.1 | 1109 |

30 games per pairing, sides alternate, MCTS roll-out depth 16.
