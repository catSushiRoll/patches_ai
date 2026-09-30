# Patches Solver — A* Search

An A* search solver + dashboard for LinkedIn's **Patches** puzzle. Patches
is LinkedIn's Shikaku-style logic game: you're given a grid with number
clues, and you fill the whole grid with non-overlapping rectangles, each
containing exactly one clue whose value equals the rectangle's area.

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
