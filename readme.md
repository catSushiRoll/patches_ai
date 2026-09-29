# Patches Solver — A* Search

An A* search solver + dashboard for LinkedIn's **Patches** puzzle. Patches
is LinkedIn's Shikaku-style logic game: you're given a grid with number
clues, and you fill the whole grid with non-overlapping rectangles, each
containing exactly one clue whose value equals the rectangle's area.

This project reads the puzzle directly from a hand-typed grid of numbers
(no OCR / no screenshot parsing) — you look at the puzzle you're playing
and type the numbers into the dashboard or into `puzzles.py`, since the
positions and values are already known once you can see the board.

## Files

- `patches_solver.py` — the A* algorithm itself: state space, successor
  (action) generation, heuristic, and the main search loop. Fully
  commented with the problem formalization.
- `puzzles.py` — helper to turn a plain grid of numbers into a `Puzzle`
  object, plus two hand-built sample puzzles (4x4 and 5x5) used to test
  the solver.
- `dashboard.py` — Streamlit dashboard: pick a sample puzzle or type in
  your own, click Solve, and watch the rectangles get placed step by
  step, with live search statistics (nodes expanded, frontier size,
  time).
- `requirements.txt` — Python dependencies.

## Running it

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

This opens a local web dashboard in your browser.

To just run the solver from the command line (no UI):

```bash
python3 -c "
from patches_solver import PatchesAStarSolver, print_solution
from puzzles import puzzle_from_grid, SAMPLE_5x5
puzzle = puzzle_from_grid(SAMPLE_5x5)
path, stats = PatchesAStarSolver(puzzle).solve()
print_solution(puzzle, path)
print(stats)
"
```

## Solving your own puzzle

Open the dashboard, choose **Custom puzzle**, set the grid size, and
type the clue numbers exactly as you see them on the puzzle, using `0`
for cells with no clue (comma-separated, one row per line). Or edit
`puzzles.py` and add your grid as a new `SAMPLE_*` constant.

## Problem formalization (for the report)

- **State**: `(filled_bitmask, remaining_clues)` — which cells are
  already covered, and which clues haven't been used by a placed
  rectangle yet.
- **Action**: place one rectangle, anchored at the first uncovered cell
  in row-major scan order, containing exactly one unused clue, with
  area equal to that clue's value.
- **Goal test**: no clues remain unused (the grid is then necessarily
  fully covered, since `sum(clue values) == rows * cols` is checked
  up front).
- **g(n)**: number of rectangles placed so far.
- **h(n)**: number of remaining unused clues. Admissible and consistent
  — provably *exact* (`h = h*`) here, because every action resolves
  exactly one clue.
- **Why the search is still efficient despite h(n) being "just a
  count"**: the real source of the algorithm's efficiency is the
  *anchor-cell rule* — at every state, only the first uncovered cell
  is ever branched on (never any other empty cell), which is the
  standard most-constrained-cell trick from exact-cover / CSP solvers.
  It collapses the branching factor from *any empty cell x any
  rectangle* down to *one fixed cell x only the rectangles that could
  cover it*.

## Notes for the report / oral defense

- Necessary (not sufficient) validity check: `sum(clue values) == rows
  * cols`. The `Puzzle` class raises a `ValueError` if this fails.
- The sample puzzles in `puzzles.py` are hand-built test cases used to
  validate the solver's logic — they are *not* copied or scraped from
  the live LinkedIn game (per the assignment's own AI-tool / academic
  integrity policy, no OCR or reproduction of the daily puzzle is
  used). Real puzzles you solve should come from typing in the numbers
  you see yourself.
- This case is **not** the 8-puzzle, Romania map, grid-maze, or N-Queens
  from lecture — it's a rectangle exact-cover / partitioning problem
  with its own state representation (bitmask + remaining-clue set),
  its own action/successor rule (anchor-cell + divisor-pair
  enumeration), and its own heuristic.