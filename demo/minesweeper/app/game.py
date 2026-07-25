"""The Minesweeper game engine, instrumented for runtime verification.

Board rules: 8x8, 10 mines, click to reveal, right-click to flag. Mine
placement is deferred to the first reveal so the first click is always safe
(and deterministic under an injected RNG).

Instrumentation is ADDITIVE: every ``Event(...)`` is built at the site of the
state change it records, beside the business logic, never in place of it. The
engine never blocks a move because a monitor might dislike it - whether a move
was legal is the monitor's verdict to make. The application's own guards
(a frozen board after a boom, a cell revealed once, a flag budget) keep
healthy play clean; the monitor is the independent check that catches a
CORRUPTED event stream that bypassed those guards.

Two correlation keys are emitted at the reveal site on purpose (see the rv
skill's key-projection note):

* game-keyed events (``game_id``) carry board-wide facts - an explosion, a
  reveal seen from the whole board, the flag count. They let a policy relate
  a reveal to the board's explosion state.
* cell-keyed events (``game_id`` + ``cell``) give each square its own
  identity, so "revealed at most once" is one rule per square.

Emitting both is additive instrumentation, not reshaped logic: the same reveal
is simply observable under both identities.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, Optional

from behave_rv.events.event import Event

# -- event vocabulary: module-level constants, referenced by name so the
#    stability analyzer can resolve them (never build a type with an f-string).
MINE_BOOM = "mine.boom"        # game-keyed: a mine was revealed; the board detonates
BOARD_REVEAL = "board.reveal"  # game-keyed: some cell was revealed on this board
CELL_REVEAL = "cell.reveal"    # cell-keyed:  this specific square was revealed
CELL_SEEN = "cell.seen"        # cell-keyed:  state latch, emitted right AFTER a first reveal
FLAG_SET = "flag.set"          # game-keyed: a flag was toggled; carries the running count
GAME_DONE = "game.done"        # game-keyed: TERMINAL - the board was cleared (a win)

SOURCE = "minesweeper"

ROWS = 8
COLS = 8
MINES = 10


def _cell_id(r: int, c: int) -> str:
    """Stable per-square identity within a board (row,col)."""
    return f"{r},{c}"


class MinesweeperGame:
    """One board. ``emit`` receives built events; ``clock`` returns strictly
    increasing event time (distinct per emit, so ordered emissions never share
    a timestamp). Both are injected so the same engine runs live (wall clock,
    events to the monitor) and under the replay gate (fake clock, events into
    a list) identically."""

    def __init__(
        self,
        game_id: str,
        emit: Callable[[Event], None],
        clock: Callable[[], float] = time.time,
        rng=None,
        rows: int = ROWS,
        cols: int = COLS,
        mines: int = MINES,
    ) -> None:
        import random

        self.game_id = game_id
        self._emit = emit
        self._clock = clock
        self._rng = rng or random.Random()
        self.rows = rows
        self.cols = cols
        self.mines = mines

        self.mine_at: set[tuple[int, int]] = set()
        self.revealed: set[tuple[int, int]] = set()
        self.flagged: set[tuple[int, int]] = set()
        self._placed = False
        self.status = "playing"        # "playing" | "won" | "lost"

    # -- emit helpers: Event(...) is built inline at each site --------------

    def _emit_board_reveal(self, r: int, c: int, mine: bool) -> None:
        self._emit(Event(BOARD_REVEAL, self._clock(),
                         {"game_id": self.game_id},
                         {"cell": _cell_id(r, c), "row": r, "col": c, "mine": mine},
                         SOURCE))

    def _emit_cell_reveal(self, r: int, c: int, mine: bool) -> None:
        self._emit(Event(CELL_REVEAL, self._clock(),
                         {"game_id": self.game_id, "cell": _cell_id(r, c)},
                         {"row": r, "col": c, "mine": mine},
                         SOURCE))

    def _emit_cell_seen(self, r: int, c: int) -> None:
        self._emit(Event(CELL_SEEN, self._clock(),
                         {"game_id": self.game_id, "cell": _cell_id(r, c)},
                         {"row": r, "col": c},
                         SOURCE))

    def _emit_boom(self, r: int, c: int) -> None:
        self._emit(Event(MINE_BOOM, self._clock(),
                         {"game_id": self.game_id},
                         {"cell": _cell_id(r, c), "row": r, "col": c},
                         SOURCE))

    def _emit_flag(self) -> None:
        self._emit(Event(FLAG_SET, self._clock(),
                         {"game_id": self.game_id},
                         {"flags": len(self.flagged), "mines": self.mines},
                         SOURCE))

    def _emit_done(self) -> None:
        self._emit(Event(GAME_DONE, self._clock(),
                         {"game_id": self.game_id},
                         {"outcome": self.status},
                         SOURCE))

    # -- board setup --------------------------------------------------------

    def _place_mines(self, safe_r: int, safe_c: int) -> None:
        """Lay mines after the first click, keeping the clicked square (and its
        neighbours) safe so the opening move always reveals something."""
        forbidden = {(safe_r, safe_c)}
        forbidden |= set(self._neighbours(safe_r, safe_c))
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols)
                 if (r, c) not in forbidden]
        self._rng.shuffle(cells)
        self.mine_at = set(cells[: self.mines])
        self._placed = True

    def _neighbours(self, r: int, c: int) -> Iterable[tuple[int, int]]:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield nr, nc

    def adjacent_count(self, r: int, c: int) -> int:
        return sum(1 for nr, nc in self._neighbours(r, c) if (nr, nc) in self.mine_at)

    # -- moves --------------------------------------------------------------

    def reveal(self, r: int, c: int) -> None:
        """Reveal a square. The application's guards keep healthy play legal:
        a finished board is frozen, and a revealed or flagged square is inert.
        The monitor enforces the same rules against a corrupted event stream."""
        if self.status != "playing":
            return                                  # guard: a frozen board stays frozen
        if (r, c) in self.revealed or (r, c) in self.flagged:
            return                                  # guard: reveal each square once
        if not self._placed:
            self._place_mines(r, c)

        if (r, c) in self.mine_at:
            # the mine square is itself a legal reveal; the boom follows it.
            self.revealed.add((r, c))
            self._emit_cell_reveal(r, c, mine=True)
            self._emit_cell_seen(r, c)
            self._emit_board_reveal(r, c, mine=True)
            self._emit_boom(r, c)                   # opens the "board detonated" scope
            self.status = "lost"
            return

        self._flood_reveal(r, c)
        self._check_win()

    def _flood_reveal(self, r: int, c: int) -> None:
        """Reveal (r,c); if it has no adjacent mines, cascade to neighbours.
        Iterative so a large open region cannot overflow the stack."""
        stack = [(r, c)]
        while stack:
            cr, cc = stack.pop()
            if (cr, cc) in self.revealed:
                continue
            if (cr, cc) in self.mine_at:
                continue
            self.revealed.add((cr, cc))
            self._emit_cell_reveal(cr, cc, mine=False)
            self._emit_cell_seen(cr, cc)
            self._emit_board_reveal(cr, cc, mine=False)
            if self.adjacent_count(cr, cc) == 0:
                stack.extend(self._neighbours(cr, cc))

    def toggle_flag(self, r: int, c: int) -> None:
        """Plant or lift a flag. The flag budget guard refuses an 11th flag,
        so healthy play never exceeds the mine count; the monitor catches a
        stream that plants more anyway."""
        if self.status != "playing":
            return
        if (r, c) in self.revealed:
            return
        if (r, c) in self.flagged:
            self.flagged.discard((r, c))
        else:
            if len(self.flagged) >= self.mines:
                return                              # guard: stay within the mine budget
            self.flagged.add((r, c))
        self._emit_flag()

    def _check_win(self) -> None:
        cleared = len(self.revealed) == self.rows * self.cols - self.mines
        if cleared and self.status == "playing":
            self.status = "won"
            self._emit_done()

    # -- view for the UI ----------------------------------------------------

    def view(self) -> dict:
        cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                revealed = (r, c) in self.revealed
                cell = {
                    "row": r, "col": c,
                    "revealed": revealed,
                    "flagged": (r, c) in self.flagged,
                    "mine": (r, c) in self.mine_at and (revealed or self.status == "lost"),
                    "count": self.adjacent_count(r, c) if revealed and (r, c) not in self.mine_at else None,
                }
                cells.append(cell)
        return {
            "game_id": self.game_id,
            "rows": self.rows, "cols": self.cols, "mines": self.mines,
            "status": self.status,
            "flags": len(self.flagged),
            "cells": cells,
        }
