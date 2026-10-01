# Patches Solver 
## Group Members

* **Syahla Fidela Pramudita** (NIM: 23/518806/TK/57166)
* **Shofura Zahratul Aisya** (NIM: 23/516971/TK/56851)

## Project Overview

This project is developed to solve LinkedIn's daily logic game **Patches** (a variant of the classic Japanese logic puzzle, Shikaku) using an **A* Search** algorithm combined with Constraint Satisfaction Problem (CSP) techniques such as **Minimum Remaining Values (MRV)** and **Forward Checking**[cite: 1, 2].

The application features a desktop Graphical User Interface (GUI) built with **Tkinter**[cite: 1]. It allows users to select preset puzzles, input custom board configurations, and watch the step-by-step rectangle allocation process visually, accompanied by real-time search statistics[cite: 1].


## File Structure

* `patches_solver.py` — Implementation of the A* Search algorithm, problem formalization (*state space*, *actions*, *transitions*, *heuristic*), forward checking, and dead-state pruning logic[cite: 1, 2].
* `puzzles.py` — Helper module to convert raw number grid matrices into structured `Puzzle` objects ready for solver execution[cite: 1, 2].
* `dashboard.py` — Tkinter-based GUI providing interactive visualization, step replay controls, real-time search logs, and execution statistics[cite: 1].

## Installation & Usage

### 1. Requirements

Ensure Python 3 is installed on your system. Tkinter comes pre-installed with standard Python distributions on Windows and macOS. For Linux (Ubuntu/Debian) users, if Tkinter is not installed, install it using:

```bash
sudo apt-get install python3-tk
```

### 2. Clone Repository
```bash
git clone git@github.com:catSushiRoll/patches_ai.git
cd patches_ai
```

### 3. Running the Desktop Application
On Windows: 
```bash
python dashboard.py
```

Or on Linux:
```bash
python3 dashboard.py
```
### 4. How to Play
