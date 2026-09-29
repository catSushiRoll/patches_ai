"""
puzzles.py  --  THIS is the file you edit to add your puzzle cases.

The dashboard reads LEVELS below automatically (File -> Load level),
so after you fill in a level here you do not need to touch any other
file.

HOW TO READ A PUZZLE FROM THE GAME
----------------------------------
Number the grid from the TOP-LEFT, starting at 0:  (row, col).
So the top-left cell is (0, 0), the cell to its right is (0, 1), and the
cell below it is (1, 0).

For every colored piece on the board write one line  S(row, col, shape, area):

  shape (look at the icon)
    "square"    plain rounded square icon
    "wide"      plain rounded rectangle, longer HORIZONTALLY
    "tall"      plain rounded rectangle, longer VERTICALLY
    "freeform"  dashed / stitched icon with little tabs on its 4 sides
    ("rectangle" = any rectangle, orientation unknown; rarely needed)

  area
    the number printed on the piece, or None if the piece shows no number

A blank cell with no icon is just an empty cell, don't write anything for it.
Sanity check: all the known areas must add up to <= rows * cols, and if
EVERY piece has a number they must add up to exactly rows * cols.
"""
from patches_solver import Puzzle, Seed


def S(row, col, shape, area=None):
    """One seed. Short helper so each piece of the puzzle fits on one line."""
    return {"pos": (row, col), "shape": shape, "area": area}


def make_puzzle(rows, cols, seed_specs) -> Puzzle:
    """Build a Puzzle from a list of S(...) dicts. Seeds are named S1, S2, ..."""
    seeds = [Seed(pos=tuple(s["pos"]), shape=s["shape"], area=s.get("area"), label=f"S{i + 1}")
             for i, s in enumerate(seed_specs)]
    return Puzzle(rows=rows, cols=cols, seeds=seeds)


# =====================================================================
# LEVELS  --  the three real cases.  Fill in "Medium" and "Hard".
# =====================================================================
LEVELS = {
    # ---------------------------------------------------------------
    # EASY: 6 x 6 grid, 6 pieces, every piece has a number
    #       (6 + 6 + 9 + 6 + 3 + 6 = 36 = 6 * 6)
    # ---------------------------------------------------------------
    "Easy": {
        "rows": 6,
        "cols": 6,
        "seeds": [
            S(0, 1, "wide", 6),        # orange
            S(1, 2, "wide", 6),        # purple
            S(2, 3, "freeform", 9),    # teal
            S(3, 2, "freeform", 6),    # red
            S(4, 3, "wide", 3),        # light blue
            S(5, 4, "wide", 6),        # gold
        ],
    },

    # ---------------------------------------------------------------
    # MEDIUM: 7 x 7 grid
    # ---------------------------------------------------------------
    "Medium": {
        "rows": 7,
        "cols": 7,
        "seeds": [ 
            # S(row, col, shape, area),
            S(1, 1, "freeform"),
            S(1, 2, "freeform", 2),
            S(1, 3, "wide"),
            S(2, 1, "freeform"),
            S(2, 2, "freeform", 2),
            S(2, 3, "freeform", 2),
            S(4, 3, "freeform", 2),
            S(4, 4, "freeform", 3),
            S(4, 5, "freeform"),
            S(5, 3, "square"),
            S(5, 4, "freeform", 2),
            S(5, 5, "freeform")
        ],
    },

    # ---------------------------------------------------------------
    # HARD
    # ---------------------------------------------------------------
    "Hard": {
        "rows": 8,
        "cols": 8,
        "seeds": [
            # S(row, col, shape, area),
            S(0, 0, "freeform"),
            S(0, 6, "freeform", 2),
            S(1, 2, "freeform", 6),
            S(1, 7, "freeform"),
            S(2, 1, "freeform", 3),
            S(2, 5, "tall", 3),
            S(3, 3, "square", 4),
            S(4, 4, "wide", 3),
            S(5, 2, "tall", 4),
            S(5, 6, "freeform", 5),
            S(6, 0, "freeform"),
            S(6, 5, "freeform", 6),
            S(7, 1, "freeform", 6),
            S(7, 7, "freeform")
        ],
    },
}


def level_is_filled(name: str) -> bool:
    lv = LEVELS[name]
    return lv["rows"] > 0 and lv["cols"] > 0 and len(lv["seeds"]) > 0


# =====================================================================
# Small hand-made test puzzles (used to sanity-check the solver).
# =====================================================================
TEST_PUZZLES = {
    "Mixed 5x5 (one unknown area)": {
        "rows": 5, "cols": 5,
        "seeds": [S(0, 0, "wide", 5), S(2, 0, "tall", 8), S(1, 3, "freeform", 6),
                  S(3, 2, "tall", 2), S(4, 4, "square", None)],
    },
    "Corners 5x5 (3 unknown freeform)": {
        "rows": 5, "cols": 5,
        "seeds": [S(0, 0, "freeform"), S(0, 4, "freeform"), S(4, 0, "freeform"), S(4, 4, "wide", 4)],
    },
}