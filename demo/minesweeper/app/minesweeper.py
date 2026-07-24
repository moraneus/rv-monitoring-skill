"""The Minesweeper game engine - monitorable by construction.

The game logic is ordinary; monitoring is ADDITIVE. Every state transition
constructs an ``Event(...)`` right at its site (the anchor the behave-rv
stability analysis keys on) and hands it to an injected ``emit`` callback,
timestamped by an injected ``clock``. The same class therefore runs live
(real monotonic clock, events to the engine) and under scripted replay
(deterministic clock, events into a list) with no change.

Event vocabulary (all types are module-level constants, referenced by name):

* ``game.started``  - a board was created (game_id).
* ``cell.reveal``   - a reveal ACTION was applied to a cell (game_id, cell).
* ``cell.revealed`` - the cell's resulting revealed STATE (game_id, cell).
                      Emitted strictly AFTER the matching ``cell.reveal`` so a
                      monitor can tell "the cell is now revealed" apart from
                      "a reveal just happened" - that gap is what lets the
                      double-reveal policy arm only after the first reveal.
* ``mine.exploded`` - a mine was uncovered; the game is lost (game_id).
* ``flag.placed``   - a flag was planted; carries the running flag count and
                      the board's mine count (game_id).
* ``flag.removed``  - a flag was cleared; carries the running count (game_id).
* ``game.over``     - informational end-of-game marker (game_id). NOT declared
                      terminal: a terminal settles prohibitions as *satisfied*
                      and frees the entity, which would blind the
                      "no reveal after a mine explodes" rule to exactly the
                      post-boom reveals it exists to catch. GC is by the
                      engine's quiescence TTL instead.
"""

from __future__ import annotations

import random
import time
import threading
from typing import Callable, Iterable, Optional

from behave_rv.events.event import Event

# --- event types: stable identities, referenced by name (never f-strings) ---
GAME_STARTED = "game.started"
CELL_REVEAL = "cell.reveal"
CELL_REVEALED = "cell.revealed"
MINE_EXPLODED = "mine.exploded"
FLAG_PLACED = "flag.placed"
FLAG_REMOVED = "flag.removed"
GAME_OVER = "game.over"

SOURCE = "minesweeper"

ROWS = 8
COLS = 8
MINES = 10


class MonotonicClock:
    """A service-relative, strictly-increasing clock.

    Verdicts are decided on event time and equal timestamps are ordered by
    content, not arrival - so two emissions whose order matters must not share
    a timestamp. Returning a value strictly greater than the previous one on
    every call makes emission order the event order, deterministically, for
    both live play and scripted traffic.
    """

    def __init__(self, start: Optional[float] = None, step: float = 1e-3):
        self._start = time.time() if start is None else start
        self._step = step
        self._last = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            now = time.time() - self._start
            if now <= self._last:
                now = self._last + self._step
            self._last = now
            return now


class DeterministicClock:
    """A scripted clock that advances a fixed step on every read.

    Used by replay_check.py and the demo so ordered emissions get distinct,
    reproducible timestamps without the caller having to tick between them.
    """

    def __init__(self, step: float = 1.0):
        self._step = step
        self._now = 0.0

    def __call__(self) -> float:
        self._now += self._step
        return self._now


def _cell_id(row: int, col: int) -> str:
    return f"{row},{col}"


class Minesweeper:
    def __init__(
        self,
        game_id: str,
        emit: Callable[[Event], None],
        clock: Callable[[], float],
        mine_positions: Optional[Iterable[tuple[int, int]]] = None,
        seed: Optional[int] = None,
    ):
        self.game_id = game_id
        self._emit = emit
        self._clock = clock
        self.rows = ROWS
        self.cols = COLS
        self.mine_count = MINES

        if mine_positions is not None:
            self.mines = set(mine_positions)
        else:
            rng = random.Random(seed)
            cells = [(r, c) for r in range(self.rows) for c in range(self.cols)]
            self.mines = set(rng.sample(cells, self.mine_count))

        self.revealed: set[tuple[int, int]] = set()
        self.flagged: set[tuple[int, int]] = set()
        self.flag_count = 0
        self.over = False
        self.exploded = False
        self.won = False

        self._emit(Event(GAME_STARTED, self._clock(), {"game_id": self.game_id},
                         {"rows": self.rows, "cols": self.cols,
                          "mines": self.mine_count}, SOURCE))

    # --- adjacency ------------------------------------------------------
    def _neighbors(self, row: int, col: int):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield nr, nc

    def _adjacent_mines(self, row: int, col: int) -> int:
        return sum(1 for nr, nc in self._neighbors(row, col)
                   if (nr, nc) in self.mines)

    # --- reveal ---------------------------------------------------------
    def reveal(self, row: int, col: int) -> None:
        """Reveal a cell. Well-behaved: no-op after game over, on a flagged
        cell, or on an already-revealed cell (the honest game never
        double-reveals; only a corrupted event can)."""
        if self.over:
            return
        if (row, col) in self.flagged:
            return
        if (row, col) in self.revealed:
            return
        self._reveal_cell(row, col)
        self._check_win()

    def _reveal_cell(self, row: int, col: int) -> None:
        cell = _cell_id(row, col)
        is_mine = (row, col) in self.mines
        self._emit(Event(CELL_REVEAL, self._clock(),
                         {"game_id": self.game_id, "cell": cell},
                         {"row": row, "col": col, "mine": is_mine}, SOURCE))
        if is_mine:
            self.exploded = True
            self.over = True
            self._emit(Event(MINE_EXPLODED, self._clock(),
                             {"game_id": self.game_id},
                             {"cell": cell}, SOURCE))
            self._emit(Event(GAME_OVER, self._clock(),
                             {"game_id": self.game_id},
                             {"result": "lost"}, SOURCE))
            return

        self.revealed.add((row, col))
        adjacent = self._adjacent_mines(row, col)
        self._emit(Event(CELL_REVEALED, self._clock(),
                         {"game_id": self.game_id, "cell": cell},
                         {"row": row, "col": col, "adjacent": adjacent}, SOURCE))
        if adjacent == 0:
            for nr, nc in self._neighbors(row, col):
                if (nr, nc) not in self.revealed and (nr, nc) not in self.flagged:
                    self._reveal_cell(nr, nc)

    def _check_win(self) -> None:
        if self.over:
            return
        if len(self.revealed) == self.rows * self.cols - self.mine_count:
            self.over = True
            self.won = True
            self._emit(Event(GAME_OVER, self._clock(),
                             {"game_id": self.game_id},
                             {"result": "won"}, SOURCE))

    # --- flag -----------------------------------------------------------
    def flag(self, row: int, col: int) -> None:
        """Toggle a flag. Well-behaved: the flag count is capped at the mine
        count, so honest play never plants more flags than there are mines."""
        if self.over:
            return
        if (row, col) in self.revealed:
            return
        cell = _cell_id(row, col)
        if (row, col) in self.flagged:
            self.flagged.discard((row, col))
            self.flag_count -= 1
            self._emit(Event(FLAG_REMOVED, self._clock(),
                             {"game_id": self.game_id},
                             {"flags": self.flag_count, "mines": self.mine_count,
                              "cell": cell}, SOURCE))
            return
        if self.flag_count >= self.mine_count:
            return
        self.flagged.add((row, col))
        self.flag_count += 1
        self._emit(Event(FLAG_PLACED, self._clock(),
                         {"game_id": self.game_id},
                         {"flags": self.flag_count, "mines": self.mine_count,
                          "cell": cell}, SOURCE))

    # --- view for the UI (no mine positions leak until game over) -------
    def view(self) -> dict:
        cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) in self.revealed:
                    state = "revealed"
                    adjacent = self._adjacent_mines(r, c)
                elif (r, c) in self.flagged:
                    state = "flagged"
                    adjacent = None
                else:
                    state = "hidden"
                    adjacent = None
                entry = {"row": r, "col": c, "state": state, "adjacent": adjacent}
                if self.over and (r, c) in self.mines:
                    entry["mine"] = True
                cells.append(entry)
        return {
            "game_id": self.game_id,
            "rows": self.rows,
            "cols": self.cols,
            "mines": self.mine_count,
            "flags": self.flag_count,
            "over": self.over,
            "exploded": self.exploded,
            "won": self.won,
            "cells": cells,
        }
