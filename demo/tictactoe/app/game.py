"""Authoritative tic-tac-toe game service - the monitorable application.

Instrumentation is additive: every lifecycle transition constructs an
``Event(...)`` directly at the site (the stability analyzer's anchor), with
module-level string constants for the event types and dict-literal
bindings/payloads. ``emit`` and ``clock`` are injected so the same code runs
live (real clock, events to the engine) and under the scripted gate (fake
clock, events into a list) with no reshaping.

Two event types, both keyed by ``game_id``:

* ``game.status`` - tracked states: started / move / won / drawn.
* ``game.over``   - the terminal: outcome won / drawn / abandoned.

Honest play can never emit a move with ``player == prev_player`` (turns
alternate) nor with ``after_finish == "yes"`` (moves on a decided board are
refused). Those fields exist so a *corrupted* producer - a move injected out
of band, bypassing this service - is caught by the monitor rather than
silently trusted. Abandonment (``game.over`` with ``abandoned``) is emitted
when an in-progress game is replaced by a new one.
"""

from __future__ import annotations

import time
import threading

from behave_rv.events.event import Event

STATUS_EVENT = "game.status"
OVER_EVENT = "game.over"
SOURCE = "tictactoe"

WINNING_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # columns
    (0, 4, 8), (2, 4, 6),              # diagonals
)


class GameOver(Exception):
    """Raised when a move is attempted on a game that is already decided."""


class IllegalMove(Exception):
    """Raised for a move on an occupied cell or out-of-range index."""


class GameService:
    """Holds the current game and applies moves, emitting events as it goes."""

    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock
        self._lock = threading.Lock()
        self._last_t = 0.0
        self._counter = 0
        # current game state
        self._game_id: str | None = None
        self._board: list[str] = [""] * 9
        self._current: str = "X"
        self._prev_mover: str = "none"
        self._move_number: int = 0
        self._decided: bool = False
        self._outcome: str | None = None

    # -- time: strictly increasing timestamps so ordered emissions never tie
    def _now(self) -> float:
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        return t

    def _new_game_id(self) -> str:
        self._counter += 1
        return f"game-{self._counter}"

    # ------------------------------------------------------------------ API
    def new_game(self) -> str:
        """Start a fresh game, abandoning any game still in progress."""
        with self._lock:
            if self._game_id is not None and not self._decided:
                # the previous game ends without being decided -> abandoned
                self._emit(Event(OVER_EVENT, self._now(), {"game_id": self._game_id},
                                 {"outcome": "abandoned"}, SOURCE))
            gid = self._new_game_id()
            self._game_id = gid
            self._board = [""] * 9
            self._current = "X"
            self._prev_mover = "none"
            self._move_number = 0
            self._decided = False
            self._outcome = None
            self._emit(Event(STATUS_EVENT, self._now(), {"game_id": gid},
                             {"status": "started"}, SOURCE))
            return gid

    def play(self, cell: int) -> dict:
        """Place the current player's mark on ``cell`` and emit the events."""
        with self._lock:
            if self._game_id is None:
                raise IllegalMove("no active game")
            if self._decided:
                # honest path refuses this; it never emits a post-decision move
                raise GameOver("game already decided")
            if not (0 <= cell < 9) or self._board[cell] != "":
                raise IllegalMove(f"cell {cell} is not playable")

            gid = self._game_id
            player = self._current
            self._board[cell] = player
            self._move_number += 1

            self._emit(Event(STATUS_EVENT, self._now(), {"game_id": gid},
                             {"status": "move", "player": player, "cell": str(cell),
                              "prev_player": self._prev_mover, "after_finish": "no",
                              "move_number": str(self._move_number)}, SOURCE))

            self._prev_mover = player
            winner = self._winner()
            if winner is not None:
                self._decided = True
                self._outcome = "won"
                self._emit(Event(STATUS_EVENT, self._now(), {"game_id": gid},
                                 {"status": "won", "winner": winner}, SOURCE))
                self._emit(Event(OVER_EVENT, self._now(), {"game_id": gid},
                                 {"outcome": "won"}, SOURCE))
            elif all(c != "" for c in self._board):
                self._decided = True
                self._outcome = "drawn"
                self._emit(Event(STATUS_EVENT, self._now(), {"game_id": gid},
                                 {"status": "drawn"}, SOURCE))
                self._emit(Event(OVER_EVENT, self._now(), {"game_id": gid},
                                 {"outcome": "drawn"}, SOURCE))
            else:
                self._current = "O" if player == "X" else "X"
            return self.state()

    def _winner(self) -> str | None:
        for a, b, c in WINNING_LINES:
            if self._board[a] != "" and self._board[a] == self._board[b] == self._board[c]:
                return self._board[a]
        return None

    def state(self) -> dict:
        return {
            "game_id": self._game_id,
            "board": list(self._board),
            "current": self._current,
            "decided": self._decided,
            "outcome": self._outcome,
            "move_number": self._move_number,
            "winner": self._winner(),
        }
