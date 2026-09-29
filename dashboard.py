"""
dashboard_tk.py
Tkinter dashboard for the Patches A* solver (square / wide / tall / freeform).
Standard library only. On Ubuntu/Debian you may need once:  sudo apt install python3-tk

Run:   python3 dashboard_tk.py

Workflow
--------
1. File -> Load level -> Easy / Medium / Hard   (cases come from puzzles.py)
   or set Rows/Cols, press "New grid", and click cells to add seeds by hand.
2. Press "Solve with A*".  The Log panel at the bottom narrates the search:
   which cell A* picked next, which seed it tried, which branches were pruned
   and why, and periodic progress lines.
3. When it finishes, drag the slider to replay the solution one cell
   assignment at a time (the red outline marks the most recent step).
"""
import queue
import threading
import tkinter as tk
from tkinter import colorchooser, messagebox, scrolledtext, ttk

from patches_solver import PatchesAStarSolver, Puzzle, Seed
from puzzles import LEVELS, TEST_PUZZLES, level_is_filled

PALETTE = ["#1DA1F2", "#0F9D58", "#8B5CF6", "#D4A017", "#008080", "#E53935", "#F57C00", "#78909C",
           "#EC407A", "#6D4C41", "#3949AB", "#AD1457", "#00897B", "#7CB342", "#5D4037", "#C2185B"]
SHAPES = ["square", "wide", "tall", "freeform"]
SHAPE_LABELS = {
    "square": "Square",
    "wide": "Wide rectangle (horizontal)",
    "tall": "Tall rectangle (vertical)",
    "freeform": "Freeform (dashed icon)",
}
LOG_TAGS = {
    "info": dict(foreground="#333333"),
    "expand": dict(foreground="#0d47a1"),
    "assign": dict(foreground="#2e7d32"),
    "prune": dict(foreground="#c62828"),
    "progress": dict(foreground="#6a1b9a"),
    "result": dict(foreground="#000000", font=("TkFixedFont", 9, "bold")),
}


# =======================================================================
# Seed add / edit dialog
# =======================================================================
class SeedDialog(tk.Toplevel):
    def __init__(self, master, pos, existing=None, used_colors=()):
        super().__init__(master)
        self.title(f"Seed at row {pos[0]}, col {pos[1]}")
        self.transient(master)
        self.result = None  # ('save', dict) | ('delete', None) | None

        start_shape = existing["shape"] if existing and existing["shape"] in SHAPES else "square"
        self.shape_var = tk.StringVar(value=start_shape)
        self.area_var = tk.StringVar(value=str(existing["area"]) if existing and existing["area"] else "")
        self.color_var = tk.StringVar(value=existing["color"] if existing else self._next_color(used_colors))

        pad = dict(padx=10, pady=6)
        tk.Label(self, text="Shape (look at the icon):").grid(row=0, column=0, sticky="nw", **pad)
        shape_frame = tk.Frame(self)
        shape_frame.grid(row=0, column=1, sticky="w", **pad)
        for s in SHAPES:
            tk.Radiobutton(shape_frame, text=SHAPE_LABELS[s], variable=self.shape_var, value=s).pack(anchor="w")

        tk.Label(self, text="Number on the piece\n(blank = no number):").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.area_var, width=8).grid(row=1, column=1, sticky="w", **pad)

        tk.Label(self, text="Color:").grid(row=2, column=0, sticky="w", **pad)
        cf = tk.Frame(self)
        cf.grid(row=2, column=1, sticky="w", **pad)
        self.swatch = tk.Label(cf, bg=self.color_var.get(), width=4, relief="ridge")
        self.swatch.pack(side="left", padx=(0, 8))
        tk.Button(cf, text="Choose...", command=self._pick_color).pack(side="left")

        bf = tk.Frame(self)
        bf.grid(row=3, column=0, columnspan=2, pady=10)
        tk.Button(bf, text="Save", width=10, command=self._on_save).pack(side="left", padx=4)
        if existing:
            tk.Button(bf, text="Delete", width=10, fg="red", command=self._on_delete).pack(side="left", padx=4)
        tk.Button(bf, text="Cancel", width=10, command=self.destroy).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        # Lock size / grab focus only AFTER the widgets exist (otherwise the
        # window freezes at Tk's tiny default size and looks blank).
        self.update_idletasks()
        self.resizable(False, False)
        self.grab_set()
        self.wait_window(self)

    @staticmethod
    def _next_color(used):
        for c in PALETTE:
            if c not in used:
                return c
        return PALETTE[0]

    def _pick_color(self):
        _, hexcode = colorchooser.askcolor(color=self.color_var.get())
        if hexcode:
            self.color_var.set(hexcode)
            self.swatch.config(bg=hexcode)

    def _on_save(self):
        txt = self.area_var.get().strip()
        area = None
        if txt:
            if not txt.isdigit() or int(txt) < 1:
                messagebox.showerror("Invalid number", "Use a positive whole number, or leave it blank.")
                return
            area = int(txt)
        self.result = ("save", {"shape": self.shape_var.get(), "area": area, "color": self.color_var.get()})
        self.destroy()

    def _on_delete(self):
        self.result = ("delete", None)
        self.destroy()


# =======================================================================
# Main application
# =======================================================================
class PatchesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Patches Solver \u2014 A* Search")
        self.rows, self.cols, self.cell = 5, 5, 56
        self.seeds = {}            # (r, c) -> {"shape", "area", "color"}   (insertion order = S1, S2, ...)
        self.solution = None       # patches_solver.Solution after a successful solve
        self.solving = False
        self.cancel_flag = threading.Event()
        self.msg_queue = queue.Queue()

        self._build_menu()
        self._build_layout()
        self._apply_grid_size()
        self._redraw()
        self.log("Ready. Load a level from File \u2192 Load level, or click cells to add seeds.", "info")

    # ------------------------------------------------------------ UI
    def _build_menu(self):
        bar = tk.Menu(self)
        fm = tk.Menu(bar, tearoff=0)

        lm = tk.Menu(fm, tearoff=0)
        for name in LEVELS:
            if level_is_filled(name):
                lm.add_command(label=name, command=lambda n=name: self.load_data(LEVELS[n], f"level {n}"))
            else:
                lm.add_command(label=f"{name}  (empty - fill it in puzzles.py)", state="disabled")
        fm.add_cascade(label="Load level", menu=lm)

        tm = tk.Menu(fm, tearoff=0)
        for name in TEST_PUZZLES:
            tm.add_command(label=name, command=lambda n=name: self.load_data(TEST_PUZZLES[n], n))
        fm.add_cascade(label="Test puzzles", menu=tm)

        fm.add_separator()
        fm.add_command(label="Clear seeds", command=self.clear_seeds)
        fm.add_command(label="Exit", command=self.destroy)
        bar.add_cascade(label="File", menu=fm)

        hm = tk.Menu(bar, tearoff=0)
        hm.add_command(label="How this A* search is formalized", command=self._show_formalization)
        bar.add_cascade(label="Help", menu=hm)
        self.config(menu=bar)

    def _build_layout(self):
        top = tk.Frame(self, padx=10, pady=8)
        top.pack(side="top", fill="x")
        tk.Label(top, text="Rows:").pack(side="left")
        self.rows_var = tk.IntVar(value=self.rows)
        tk.Spinbox(top, from_=2, to=12, width=4, textvariable=self.rows_var).pack(side="left", padx=(2, 10))
        tk.Label(top, text="Cols:").pack(side="left")
        self.cols_var = tk.IntVar(value=self.cols)
        tk.Spinbox(top, from_=2, to=12, width=4, textvariable=self.cols_var).pack(side="left", padx=(2, 10))
        tk.Button(top, text="New grid", command=self.new_grid).pack(side="left", padx=(0, 20))
        self.solve_btn = tk.Button(top, text="\u25b6 Solve with A*", bg="#2E7D32", fg="white",
                                   command=self.on_solve_clicked)
        self.solve_btn.pack(side="left")
        self.cancel_btn = tk.Button(top, text="Cancel", command=self.on_cancel_clicked, state="disabled")
        self.cancel_btn.pack(side="left", padx=(6, 20))
        self.verbose_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="Verbose log (every expansion)", variable=self.verbose_var).pack(side="left")

        body = tk.Frame(self)
        body.pack(side="top", fill="both")
        self.canvas = tk.Canvas(body, bg="white", highlightthickness=1, highlightbackground="#999")
        self.canvas.pack(side="left", padx=10, pady=6)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        side = tk.Frame(body, padx=10, pady=6)
        side.pack(side="left", fill="y")
        tk.Label(side, text="Seeds  (label, position, shape, number)", font=("", 10, "bold")).pack(anchor="w")
        self.seed_list = tk.Listbox(side, width=36, height=10, activestyle="none")
        self.seed_list.pack(pady=(2, 8))
        self.status_label = tk.Label(side, text="", fg="#333", wraplength=260, justify="left")
        self.status_label.pack(anchor="w", pady=(0, 4))
        self.progress = ttk.Progressbar(side, mode="indeterminate", length=240)
        self.stats_label = tk.Label(side, text="", justify="left", fg="#555")
        self.stats_label.pack(anchor="w", pady=(4, 6))
        tk.Label(side, text="Replay: cells assigned so far").pack(anchor="w")
        self.step_var = tk.IntVar(value=0)
        self.step_scale = tk.Scale(side, from_=0, to=0, orient="horizontal", variable=self.step_var,
                                   command=lambda _e: self._redraw(), length=240, state="disabled")
        self.step_scale.pack(anchor="w")

        logbox = tk.LabelFrame(self, text=" Log ", padx=6, pady=4)
        logbox.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(logbox, height=12, width=110, wrap="none",
                                                  font=("TkFixedFont", 9), state="disabled")
        self.log_text.pack(fill="both", expand=True)
        for tag, cfg in LOG_TAGS.items():
            self.log_text.tag_configure(tag, **cfg)
        tk.Button(logbox, text="Clear log", command=self.clear_log).pack(anchor="e", pady=(4, 0))

    # ------------------------------------------------------------ log
    def log(self, msg, kind="info"):
        t = self.log_text
        t.config(state="normal")
        t.insert("end", msg + "\n", kind)
        n = int(t.index("end-1c").split(".")[0])
        if n > 4000:
            t.delete("1.0", f"{n - 3500}.0")
        t.see("end")
        t.config(state="disabled")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ------------------------------------------------------------ grid / seeds
    def _apply_grid_size(self):
        self.cell = max(30, min(60, 480 // max(self.rows, self.cols)))
        self.canvas.config(width=self.cols * self.cell + 2, height=self.rows * self.cell + 2)

    def _reset_solution(self):
        self.solution = None
        self.step_scale.config(to=0, state="disabled")
        self.step_var.set(0)

    def new_grid(self):
        if self.solving:
            return
        if self.seeds and not messagebox.askyesno("New grid", "This clears all current seeds. Continue?"):
            return
        self.rows, self.cols = self.rows_var.get(), self.cols_var.get()
        self.seeds = {}
        self._reset_solution()
        self._apply_grid_size()
        self.status_label.config(text="Click a cell to add a seed.")
        self.stats_label.config(text="")
        self._refresh_seed_list()
        self._redraw()

    def clear_seeds(self):
        if self.solving:
            return
        self.seeds = {}
        self._reset_solution()
        self._refresh_seed_list()
        self._redraw()

    def load_data(self, data, title):
        if self.solving:
            return
        self.rows, self.cols = data["rows"], data["cols"]
        self.rows_var.set(self.rows)
        self.cols_var.set(self.cols)
        self.seeds = {}
        for i, s in enumerate(data["seeds"]):
            self.seeds[tuple(s["pos"])] = {"shape": s["shape"], "area": s["area"], "color": PALETTE[i % len(PALETTE)]}
        self._reset_solution()
        self._apply_grid_size()
        self.status_label.config(text=f"Loaded {title}. Press Solve.")
        self.stats_label.config(text="")
        self._refresh_seed_list()
        self._redraw()
        self.log(f"Loaded {title}: {self.rows}x{self.cols} grid, {len(self.seeds)} seeds.", "info")

    def _refresh_seed_list(self):
        self.seed_list.delete(0, "end")
        for i, (pos, s) in enumerate(self.seeds.items()):
            num = s["area"] if s["area"] is not None else "-"
            self.seed_list.insert("end", f"S{i + 1}  ({pos[0]},{pos[1]})  {s['shape']:<8}  {num}")
            self.seed_list.itemconfig(i, background=s["color"], foreground="white")

    def on_canvas_click(self, event):
        if self.solving:
            return
        r, c = event.y // self.cell, event.x // self.cell
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return
        pos = (r, c)
        used = {s["color"] for p, s in self.seeds.items() if p != pos}
        dlg = SeedDialog(self, pos, existing=self.seeds.get(pos), used_colors=used)
        if dlg.result is None:
            return
        action, data = dlg.result
        if action == "delete":
            self.seeds.pop(pos, None)
        else:
            self.seeds[pos] = data
        self._reset_solution()
        self._refresh_seed_list()
        self._redraw()

    # ------------------------------------------------------------ solving
    def on_solve_clicked(self):
        if self.solving:
            return
        if not self.seeds:
            messagebox.showinfo("No seeds", "Add at least one seed first (or load a level).")
            return
        try:
            seed_objs = [Seed(pos=p, shape=s["shape"], area=s["area"], label=f"S{i + 1}")
                         for i, (p, s) in enumerate(self.seeds.items())]
            puzzle = Puzzle(rows=self.rows, cols=self.cols, seeds=seed_objs)
        except ValueError as e:
            messagebox.showerror("Invalid puzzle", str(e))
            return

        self._reset_solution()
        self._redraw()
        self.solving = True
        self.cancel_flag.clear()
        self.solve_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress.pack(anchor="w", pady=(0, 6))
        self.progress.start(12)
        self.status_label.config(text="Searching...")
        self.stats_label.config(text="")
        self.log("\u2500" * 60, "info")
        self.log("Solving with A* ...", "result")

        verbose = self.verbose_var.get()  # read here: Tk variables must not be touched from the worker thread

        def worker():
            def push(msg, kind="info"):
                self.msg_queue.put(("log", msg, kind))
            solution, stats = PatchesAStarSolver(puzzle).solve(
                verbose=verbose, should_stop=self.cancel_flag.is_set, log=push)
            self.msg_queue.put(("done", solution, stats))

        threading.Thread(target=worker, daemon=True).start()
        self.after(40, self._poll_queue)

    def on_cancel_clicked(self):
        self.cancel_flag.set()
        self.status_label.config(text="Cancelling...")

    def _poll_queue(self):
        done = None
        for _ in range(400):  # cap per tick so the window stays responsive
            try:
                item = self.msg_queue.get_nowait()
            except queue.Empty:
                break
            if item[0] == "log":
                self.log(item[1], item[2])
            else:
                done = item
                break
        if done is None:
            self.after(40, self._poll_queue)
        else:
            self._on_done(done[1], done[2])

    def _on_done(self, solution, stats):
        self.solving = False
        self.progress.stop()
        self.progress.pack_forget()
        self.solve_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

        self.stats_label.config(
            text=(f"Nodes expanded:  {stats['nodes_expanded']}\n"
                  f"Nodes generated: {stats['nodes_generated']}\n"
                  f"Nodes pruned:    {stats['nodes_pruned']}\n"
                  f"Max frontier:    {stats['max_frontier']}\n"
                  f"Time:            {stats['elapsed_sec'] * 1000:.1f} ms"))

        if stats.get("cancelled"):
            self.status_label.config(text="Cancelled.")
        elif solution is None:
            self.status_label.config(text="No valid solution exists for this puzzle.")
        else:
            self.solution = solution
            n = len(solution.steps)
            self.status_label.config(text=f"Solved: {n} cells assigned by A*.")
            self.step_scale.config(to=n, state="normal")
            self.step_var.set(n)
            self.log("Solution (per seed):", "result")
            for k, reg in enumerate(solution.regions):
                cells = ", ".join(f"({r},{c})" for r, c in sorted(reg.cells))
                self.log(f"  {reg.seed.name} {reg.seed.shape:<8} {reg.area:>2} cells: {cells}", "result")
            self.log(f"Done in {stats['elapsed_sec'] * 1000:.1f} ms. "
                     f"Expanded {stats['nodes_expanded']}, pruned {stats['nodes_pruned']} nodes. "
                     f"Use the slider to replay it.", "result")
        self._redraw()

    # ------------------------------------------------------------ drawing
    @staticmethod
    def _tint(hexcolor, t=0.55):
        h = hexcolor.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        r, g, b = (int(v + (255 - v) * t) for v in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _redraw(self):
        cv, cell = self.canvas, self.cell
        cv.delete("all")
        W, H = self.cols * cell, self.rows * cell
        items = list(self.seeds.items())

        owner = {}
        n_steps = 0
        if self.solution:
            n_steps = self.step_var.get()
            for k, (pos, _) in enumerate(items):
                owner[pos] = k
            for pos, k in self.solution.steps[:n_steps]:
                owner[pos] = k
            for (r, c), k in owner.items():
                cv.create_rectangle(c * cell, r * cell, (c + 1) * cell, (r + 1) * cell,
                                    fill=self._tint(items[k][1]["color"]), outline="")

        for i in range(self.rows + 1):
            cv.create_line(0, i * cell, W, i * cell, fill="#d0d0d0")
        for j in range(self.cols + 1):
            cv.create_line(j * cell, 0, j * cell, H, fill="#d0d0d0")

        for (r, c), k in owner.items():   # thick outline around each region
            x0, y0, x1, y1 = c * cell, r * cell, (c + 1) * cell, (r + 1) * cell
            if owner.get((r - 1, c)) != k:
                cv.create_line(x0, y0, x1, y0, width=3)
            if owner.get((r + 1, c)) != k:
                cv.create_line(x0, y1, x1, y1, width=3)
            if owner.get((r, c - 1)) != k:
                cv.create_line(x0, y0, x0, y1, width=3)
            if owner.get((r, c + 1)) != k:
                cv.create_line(x1, y0, x1, y1, width=3)

        for k, ((r, c), s) in enumerate(items):
            self._draw_seed_icon(r, c, k, s)

        if self.solution and n_steps > 0:   # mark the most recent step
            (r, c), _ = self.solution.steps[n_steps - 1]
            cv.create_rectangle(c * cell + 2, r * cell + 2, (c + 1) * cell - 2, (r + 1) * cell - 2,
                                outline="#d50000", width=2)

    def _draw_seed_icon(self, r, c, k, s):
        cv, cell = self.canvas, self.cell
        pad = int(cell * 0.17)
        x0, y0, x1, y1 = c * cell + pad, r * cell + pad, (c + 1) * cell - pad, (r + 1) * cell - pad
        w, h = x1 - x0, y1 - y0
        shape = s["shape"]
        if shape == "wide":
            y0, y1 = y0 + h * 0.22, y1 - h * 0.22
        elif shape == "tall":
            x0, x1 = x0 + w * 0.22, x1 - w * 0.22
        if shape == "freeform":
            cv.create_rectangle(x0, y0, x1, y1, fill=s["color"], outline="black", width=2, dash=(3, 2))
        else:
            cv.create_rectangle(x0, y0, x1, y1, fill=s["color"], outline="black", width=1)
        if s["area"] is not None:
            cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=str(s["area"]), fill="white",
                           font=("", max(9, cell // 5), "bold"))
        cv.create_text(c * cell + 3, r * cell + 2, text=f"S{k + 1}", anchor="nw", fill="#555", font=("", 7))

    def _show_formalization(self):
        messagebox.showinfo("A* formalization", (
            "State: for every seed, the set of cells it owns so far.\n\n"
            "Action: pick ONE empty cell (the one with the fewest possible owners - "
            "'minimum remaining values') and assign it to ONE seed that could still "
            "legally own it. Cost 1 per action.\n\n"
            "Goal: no empty cell left and every region valid (exact square / wide / tall "
            "rectangle, or a connected freeform blob, with the right area).\n\n"
            "g(n): cells assigned so far.  h(n): empty cells left - admissible, consistent "
            "and exact. States that can no longer reach a goal (h = infinity) are pruned "
            "at once: a seed with no valid placement left, a region cut off, a cell nobody "
            "can own, or an impossible area budget.\n\n"
            "Since g+h is constant for live nodes, ties go to the deeper node; the real "
            "speed comes from MRV cell choice plus this early pruning."))


if __name__ == "__main__":
    PatchesApp().mainloop()