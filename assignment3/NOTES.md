# Assignment 3 notes: ARC-AGI-1 solver (Part 3)

Run: `python run.py 007bbfb7 25ff71a9 ...` (tasks are in `tasks/`; set `ARC_DATA` to use the full dataset).

## 1. Formulation
- **Task:** a few demo pairs (input grid, output grid) plus a test input. Find the transformation, apply it to the test input.
- **Action:** one DSL function grid -> grid (flip, rotate, crop to object, upscale, tile, mirror, gravity, fill holes, recolour, ...). About 33 fixed actions plus colour-parameterised ones built from the colours seen in the demos.
- **State:** the tuple of grids obtained by running the program so far on ALL demo inputs at once.
- **Goal test:** every one of those grids equals its demo output. There is no stated goal at test time, so "matches all demos" stands in for it.
- **Solution:** the sequence of actions (a program). It is then run on the test input and compared to the hidden test output.
- **Heuristic / signal:** number of differing cells between the current grids and the demo outputs. It is not used to steer the search; it only ranks the closest program when nothing solves the task.

## 2. Algorithm and why
Breadth-first search over programs, depth up to 3, 20 s limit per task, with a visited set so two programs giving the same grids on the demos are not expanded twice.
- BFS gives the shortest program first, and a shorter program is less likely to be a coincidence that fits only the demos.
- DFS could waste time in deep useless chains and gives long programs.
- A* / greedy would need a trustworthy heuristic, and mismatch count is not one: a wrong-looking intermediate grid (a rotation, a crop) often precedes the right answer.
- Random search, GA or SA (from Assignment 1) have no useful notion of "slightly better program" here.

## 3. Instances tested (10 official ARC-AGI-1 training tasks)
| Task | Result | Program found | What the task needs |
|---|---|---|---|
| 007bbfb7 | solved | fractal | place a copy of the grid wherever it has a filled cell |
| 3c9b0459 | solved | rot180 | rotate 180 |
| 6150a2bd | solved | rot180 | rotate 180 |
| 68b16354 | solved | flip_v | vertical flip |
| a416b8f3 | solved | tile2x2, top_half | repeat the grid side by side |
| c8f0f002 | solved | recolor_7_5 | change colour 7 to 5 |
| 7468f01a | solved | flip_h, crop_content | crop the object and mirror it |
| 25ff71a9 | failed | (closest: sym_v, gravity_down) | move the object down by one row |
| 4258a5f9 | failed | none | draw a ring of 1s around every 5 |
| d10ecb37 | failed | none (timed out at depth 3) | crop the top-left 2x2 corner |

7 of 10 correct on the held-out test pair, 0 programs that fit the demos but failed the test.
Extra (not required): on the first 165 training tasks (alphabetical order, run stopped early) it got 19 correct, about 11%, again with 0 demo-fit-but-wrong programs.

## 4. Failure analysis
**25ff71a9.** Demo: a row of 1s at the top moves one row down. No action shifts the grid by one cell. `gravity_down` pushes it to the bottom, which is wrong for any grid taller than 2 rows, so no program fits all demos. To fix it, add `shift(dr, dc)` actions (about 4 more). Then the program is one action long. **4258a5f9.** The output paints a 3x3 ring around each 5. This is a local rule ("cells next to a 5 become 1"), not a whole-grid function. The DSL cannot express it, so deeper search never helps. Fixing it needs a different kind of action, such as "stamp this pattern around every object". **d10ecb37.** The answer is the top-left corner of size 2x2, but only `crop` to an object or bounding box exists, so nothing matches. Needs a "crop corner of size k" action, with k read from the output size.

## 5. Scaling and limits
- Branching factor b is about 30 fixed actions plus about 10 recolours per colour pair seen, so roughly 100-200 per step, and search cost grows like b^depth. d10ecb37 expanded 240,000 nodes and hit the time limit at depth 3. Depth 4 would mean tens of millions.
- The visited set (deduping equal grids) is the only thing keeping depth 3 feasible.
- Harder tasks (ARC-AGI-2) need many steps with rules that depend on context, so the program length grows and brute force dies. The failures above show the other limit: if the right action is missing from the DSL, no amount of search finds it.

## 6. Link to Chollet's thesis
- The solver shows **skill, not skill-acquisition efficiency**. The skill comes from a DSL written by a human who had already looked at ARC-style tasks. It only works on tasks that fit those primitives, and it learns nothing between tasks.
- Hard-coded priors: objects (connected components, largest/smallest), geometry (flips, rotations, symmetry, tiling), gravity/containment (holes), colour identity, "dominant colour" (a form of counting). These are close to Core Knowledge, but choosing exactly these functions is where my own knowledge of ARC leaks in. It matters: it is the "buying skill with priors" that Chollet criticises.
- It does show a small piece of efficiency: it learns a task from 2-4 demos alone, with no training data.

## 7. LLM use
Claude helped write the DSL, search and runner code. What I must be able to state in the exam: it contributed the code skeleton and the list of candidate primitives; I verified it by running it on the tasks and checking that every found program is run on a held-out test output (the solver never sees it while searching). Where unreliable: it can propose primitives that sound useful but do nothing for the tasks, and it cannot tell you which primitive a given unsolved task needs without looking at the grids. (Edit this paragraph to say what YOU actually did.)

## 8. What I learned
- Many ARC tasks really are a short chain of simple operations, and a small search finds them fast, but the DSL is the real bottleneck.
- Fitting the demos is not proof: that is why the test pair is checked separately, even though no overfit case happened here.
- Classical search is fast and explainable, and fails on anything outside its vocabulary, and its cost explodes with the number of steps.
