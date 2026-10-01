"""
patches_solver.py
A* solver for LinkedIn's "Patches" puzzle (a Shikaku-style puzzle).

THE PUZZLE
==========
A grid contains colored SEED cells. The grid must be partitioned into one
region per seed, covering every cell exactly once (no overlaps, no gaps),
and each region contains exactly its own seed. EVERY region is an
axis-aligned rectangle (a square counts as a rectangle). What differs per
seed is the kind of rectangle it may become (read from the icon):

  'square'  plain square icon           -> W == H
  'wide'    plain, longer horizontally  -> W >  H
  'tall'    plain, longer vertically    -> H >  W
  'any'     dashed icon with side tabs  -> any rectangle (W, H free)
            (older name: 'freeform' / 'rectangle' -- accepted as aliases;
             the dashed icon does NOT mean an irregular shape)

and, optionally, an AREA (the number printed on the piece, or None).

FORMALIZATION AS A SEARCH PROBLEM
=================================
State   : tuple of K bitmasks, owned[k] = cells currently assigned to seed
          k. Initially owned[k] is just seed k's own cell.
Action  : take ONE empty cell x and assign it to ONE seed k that could
          still legally own it. Cost of an action = 1.
Goal    : no empty cell is left and every region is a valid rectangle.

Which cell x?  "Minimum Remaining Values" (MRV): the empty cell with the
FEWEST candidate owners (ties -> first in row-major order). Branching on
that cell is complete (every cell must be owned by someone, so trying all
its candidate owners loses no solution) but keeps branching tiny.

Candidate owners / pruning. For every seed we precompute its DOMAIN: all
rectangle placements with the right shape and area that contain the seed
cell and no other seed cell. In a given state a placement is still ALIVE
if it contains everything the seed already owns and touches no cell owned
by another seed. From the alive placements we get:
  * allowed cells of seed k = union of its alive placements (cell x can
    only be given to k if some alive placement of k contains x);
  * forced cells = intersection of its alive placements (nobody else may
    take them);
  * dead state if a seed has no alive placement, or an empty cell has no
    allowed owner, or the area budget is impossible (empty cells minus the
    needs of numbered seeds = "slack" that unnumbered seeds may absorb).
All of these are NECESSARY conditions, so pruning never loses a solution.

HEURISTIC
---------
h(n) = number of empty cells left. Every action fills exactly one cell, so
from any live state the true remaining cost is exactly h(n): admissible,
consistent and exact (h = h*). Dead states get h = infinity.
Because g + h is the same for every live node, f never ranks nodes; ties
go to the DEEPER node (larger g), so A* dives toward the goal. The speed
comes from MRV and dead-state pruning, not from f (worth saying honestly
in the report).
"""

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple
import heapq
import itertools
import time

Coord = Tuple[int, int]

VALID_SHAPES = {"square", "wide", "tall", "any"}
_ALIASES = {"freeform": "any", "rectangle": "any"}

_popcount = int.bit_count if hasattr(int, "bit_count") else (lambda x: bin(x).count("1"))


def _iter_bits(mask: int):
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


def normalize_shape(shape: str) -> str:
    shape = _ALIASES.get(shape, shape)
    if shape not in VALID_SHAPES:
        raise ValueError(f"Unknown shape {shape!r}; must be one of {sorted(VALID_SHAPES)} "
                         f"(or the aliases {sorted(_ALIASES)}).")
    return shape


@dataclass(frozen=True)
class Seed:
    pos: Coord
    shape: str                  # 'square' | 'wide' | 'tall' | 'any'
    area: Optional[int] = None  # None if the piece shows no number
    label: str = ""              # display name, e.g. "S1"

    def __post_init__(self):
        object.__setattr__(self, "shape", normalize_shape(self.shape))
        if self.area is not None and self.area < 1:
            raise ValueError(f"Seed at {self.pos} has a non-positive area.")

    @property
    def name(self) -> str:
        return self.label or f"seed{self.pos}"


@dataclass
class Puzzle:
    rows: int
    cols: int
    seeds: List[Seed]

    def __post_init__(self):
        seen = set()
        for s in self.seeds:
            r, c = s.pos
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                raise ValueError(f"Seed at {s.pos} is outside the {self.rows}x{self.cols} grid.")
            if s.pos in seen:
                raise ValueError(f"Two seeds share the same cell {s.pos}.")
            seen.add(s.pos)
        known_sum = sum(s.area for s in self.seeds if s.area is not None)
        if known_sum > self.rows * self.cols:
            raise ValueError(f"Known areas already sum to {known_sum}, more than the "
                             f"grid's {self.rows * self.cols} cells.")


@dataclass
class Region:
    cells: FrozenSet[Coord]
    seed: Seed

    @property
    def area(self) -> int:
        return len(self.cells)


@dataclass
class Solution:
    steps: List[Tuple[Coord, int]]  # (cell, seed index) in the order A* assigned them
    regions: List[Region]           # one per seed, same order as puzzle.seeds


def _shape_ok(shape, w, h):
    if shape == "square":
        return w == h
    if shape == "wide":
        return w > h
    if shape == "tall":
        return h > w
    return True  # 'any'


class PatchesAStarSolver:
    DETAIL_LIMIT = 150      # expansions logged in full when not verbose
    PROGRESS_EVERY = 250    # progress line period afterwards

    def __init__(self, puzzle: Puzzle):
        self.puzzle = puzzle
        self.R, self.C = puzzle.rows, puzzle.cols
        self.N = self.R * self.C
        self.full = (1 << self.N) - 1
        self.seeds = list(puzzle.seeds)
        self.K = len(self.seeds)
        self.seed_bit = [1 << (s.pos[0] * self.C + s.pos[1]) for s in self.seeds]
        self.nb = self._neighbor_masks()
        self.domain: List[List[int]] = [self._build_domain(k) for k in range(self.K)]

    # ---------------- precomputation ----------------
    def _coord(self, i):
        return divmod(i, self.C)

    def _neighbor_masks(self):
        nb = []
        for i in range(self.N):
            r, c = divmod(i, self.C)
            m = 0
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.R and 0 <= cc < self.C:
                    m |= 1 << (rr * self.C + cc)
            nb.append(m)
        return nb

    def _rect_mask(self, r0, c0, h, w):
        m = 0
        for r in range(r0, r0 + h):
            m |= ((1 << w) - 1) << (r * self.C + c0)
        return m

    def _build_domain(self, k):
        """All rectangles that could ever be seed k's final region."""
        seed = self.seeds[k]
        sr, sc = seed.pos
        others = 0
        for j, b in enumerate(self.seed_bit):
            if j != k:
                others |= b
        out = []
        for h in range(1, self.R + 1):
            for w in range(1, self.C + 1):
                if seed.area is not None and w * h != seed.area:
                    continue
                if not _shape_ok(seed.shape, w, h):
                    continue
                for r0 in range(max(0, sr - h + 1), min(sr, self.R - h) + 1):
                    for c0 in range(max(0, sc - w + 1), min(sc, self.C - w) + 1):
                        m = self._rect_mask(r0, c0, h, w)
                        if not (m & others):
                            out.append(m)
        return out

    # ---------------- state analysis (forward checking + MRV) ----------------
    def _analyze(self, owned: Tuple[int, ...]):
        """
        Returns one of
          ("dead", reason)                 -> state cannot reach a goal
          ("goal", None)                   -> complete and valid
          ("ok", (cell_index, candidates)) -> MRV cell and its candidate seeds
        """
        allm = 0
        for m in owned:
            allm |= m
        empty = self.full & ~allm
        n_empty = _popcount(empty)

        # Area budget: numbered seeds still need (area - owned) cells; whatever
        # is left ("slack") is all that unnumbered seeds can still absorb.
        needs = 0
        for k, seed in enumerate(self.seeds):
            if seed.area is not None:
                needs += seed.area - _popcount(owned[k])
        if needs > n_empty:
            return ("dead", f"numbered pieces still need {needs} cells but only {n_empty} are empty")
        slack = n_empty - needs

        allowed = [0] * self.K
        forced = []
        for k, seed in enumerate(self.seeds):
            ok = owned[k]
            cnt = _popcount(ok)
            unknown = seed.area is None
            others = allm & ~ok
            found = 0
            inter = self.full
            for rm in self.domain[k]:
                if rm & others or ok & ~rm:
                    continue
                if unknown and _popcount(rm) - cnt > slack:
                    continue
                found |= rm
                inter &= rm
            if not found:
                return ("dead", f"{seed.name} ({seed.shape}) has no valid rectangle left")
            allowed[k] = found & empty
            forced.append((k, inter & empty))

        # Cells a seed MUST own (in every alive placement) cannot go to anyone else.
        for k, cells in forced:
            if cells:
                for j in range(self.K):
                    if j != k:
                        allowed[j] &= ~cells

        if not empty:
            return ("goal", None)

        # Bit-sliced candidate counts: atN = cells with at least N candidate owners.
        at1 = at2 = at3 = at4 = 0
        for a_k in allowed:
            at4 |= at3 & a_k
            at3 |= at2 & a_k
            at2 |= at1 & a_k
            at1 |= a_k
        orphan = empty & ~at1
        if orphan:
            x = (orphan & -orphan).bit_length() - 1
            return ("dead", f"cell {self._coord(x)} has no possible owner")
        for level in (at1 & ~at2, at2 & ~at3, at3 & ~at4, at4):
            pick = empty & level
            if pick:
                break
        x = (pick & -pick).bit_length() - 1   # MRV cell; ties -> first in row-major order
        cands = [k for k in range(self.K) if (allowed[k] >> x) & 1]
        cands.sort(key=lambda k: (0 if self.nb[x] & owned[k] else 1, _popcount(owned[k]), k))
        return ("ok", (x, cands))

    # ---------------- A* main loop ----------------
    def solve(self, verbose: bool = False, should_stop: Optional[Callable[[], bool]] = None,
              log: Optional[Callable[[str, str], None]] = None):
        """
        Returns (Solution | None, stats).
        log(msg, kind) gets human-readable lines; kind in
        'info', 'expand', 'assign', 'prune', 'progress', 'result'.
        should_stop() is polled regularly; returning True cancels the search.
        """
        def emit(msg, kind="info"):
            if log is not None:
                log(msg, kind)

        t0 = time.perf_counter()
        stats = dict(nodes_expanded=0, nodes_generated=1, nodes_pruned=0, max_frontier=1,
                     elapsed_sec=0.0, solution_length=None, cancelled=False, reason=None)

        def finish(sol, reason=None):
            stats["elapsed_sec"] = time.perf_counter() - t0
            stats["reason"] = reason
            return sol, stats

        emit(f"Puzzle: {self.R}x{self.C} grid, {self.K} seeds, {self.N - self.K} cells to assign.")
        for k, s in enumerate(self.seeds):
            emit(f"  {s.name} at {s.pos}: {s.shape}, area={s.area if s.area is not None else '?'}, "
                 f"{len(self.domain[k])} candidate rectangles")

        known = [s.area for s in self.seeds if s.area is not None]
        unknown = self.K - len(known)
        if not unknown and sum(known) != self.N:
            emit(f"Pre-check FAILED: all areas are known but sum to {sum(known)}, not {self.N}.", "prune")
            return finish(None, "area-sum-mismatch")
        if sum(known) + unknown > self.N:
            emit("Pre-check FAILED: known areas + one cell per unnumbered seed exceed the grid.", "prune")
            return finish(None, "too-many-cells")

        emit("Heuristic: h(n) = number of empty cells (exact). Dead states are pruned (h = inf).")
        emit("f = g + h is constant for live nodes, so ties go to the deeper node; "
             "MRV cell choice + dead-state pruning do the real work.")

        start = tuple(self.seed_bit)
        status, data = self._analyze(start)
        if status == "dead":
            emit(f"Start state is already dead: {data}", "prune")
            return finish(None, "dead-start")

        counter = itertools.count()
        h0 = self.N - self.K
        heap = [(h0, 0, next(counter), start, status, data)]
        parent = {start: None}
        best_depth = 0
        loops = 0

        while heap:
            loops += 1
            if should_stop is not None and loops % 20 == 0 and should_stop():
                stats["cancelled"] = True
                emit("Search cancelled by user.", "info")
                return finish(None, "cancelled")

            stats["max_frontier"] = max(stats["max_frontier"], len(heap))
            f, negg, _, owned, status, data = heapq.heappop(heap)
            g = -negg
            stats["nodes_expanded"] += 1
            n = stats["nodes_expanded"]
            best_depth = max(best_depth, g)

            if status == "goal":
                emit(f"GOAL reached at expansion #{n}: every cell assigned, every region a valid rectangle.",
                     "result")
                stats["solution_length"] = g
                return finish(self._build_solution(owned, parent), None)

            x, cands = data
            detailed = verbose or n <= self.DETAIL_LIMIT
            if detailed:
                names = ", ".join(self.seeds[k].name for k in cands)
                emit(f"#{n} expand (g={g}, h={self.N - self.K - g}): next cell {self._coord(x)} "
                     f"has {len(cands)} candidate owner(s): {names}", "expand")
            elif n % self.PROGRESS_EVERY == 0:
                emit(f"progress: expanded {n}, frontier {len(heap)}, generated {stats['nodes_generated']}, "
                     f"pruned {stats['nodes_pruned']}, deepest g={best_depth}/{self.N - self.K}", "progress")

            for k in cands:
                child = owned[:k] + (owned[k] | (1 << x),) + owned[k + 1:]
                if child in parent:
                    continue
                cstatus, cdata = self._analyze(child)
                if cstatus == "dead":
                    stats["nodes_pruned"] += 1
                    if detailed:
                        emit(f"    x prune: {self._coord(x)} -> {self.seeds[k].name}: {cdata}", "prune")
                    continue
                parent[child] = (owned, x, k)
                g2 = g + 1
                h2 = self.N - sum(_popcount(m) for m in child)
                heapq.heappush(heap, (g2 + h2, -g2, next(counter), child, cstatus, cdata))
                stats["nodes_generated"] += 1
                if detailed:
                    emit(f"    + assign {self._coord(x)} -> {self.seeds[k].name}  (g={g2}, h={h2})", "assign")

        emit("Frontier exhausted: no valid partition exists for this puzzle.", "prune")
        return finish(None, "exhausted")  

    def _build_solution(self, owned, parent) -> Solution:
        steps = []
        cur = owned
        while parent[cur] is not None:
            prev, x, k = parent[cur]
            steps.append((self._coord(x), k))
            cur = prev
        steps.reverse()
        regions = [Region(frozenset(self._coord(i) for i in _iter_bits(owned[k])), self.seeds[k])
                   for k in range(self.K)]
        return Solution(steps=steps, regions=regions)

    # ---------------- uniqueness check ----------------
    def count_solutions(self, limit: int = 2, should_stop: Optional[Callable[[], bool]] = None):
        """
        Counts distinct valid partitions, stopping at `limit`.
        Returns (count, finished). finished=False if cancelled first.
        A well-designed Patches puzzle has exactly 1.
        """
        count = 0
        stack = [tuple(self.seed_bit)]
        steps = 0
        while stack:
            steps += 1
            if should_stop is not None and steps % 50 == 0 and should_stop():
                return count, False
            owned = stack.pop()
            status, data = self._analyze(owned)
            if status == "dead":
                continue
            if status == "goal":
                count += 1
                if count >= limit:
                    return count, True
                continue
            x, cands = data
            for k in cands:
                stack.append(owned[:k] + (owned[k] | (1 << x),) + owned[k + 1:])
        return count, True


def print_solution(puzzle: Puzzle, solution: Solution):
    grid = [["." for _ in range(puzzle.cols)] for _ in range(puzzle.rows)]
    for k, region in enumerate(solution.regions):
        label = chr(ord("A") + k % 26)
        for r, c in region.cells:
            grid[r][c] = label
    for row in grid:
        print(" ".join(row))