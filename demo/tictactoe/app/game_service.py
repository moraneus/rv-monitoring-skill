"""Tic-tac-toe game logic with additive behave-rv instrumentation.

The service is a CORRECT implementation of the game: it rejects moves out of
turn, on an occupied cell, or after the game is over. Its only coupling to
monitoring is an injected ``emit`` callback it calls at each observable state
change -- the business logic is never reshaped to be observable. The same
service runs live (real queue + clock) and under the deterministic replay gate
(fake clock, events into a list).

Event vocabulary emitted (the shouter side of the contract):

* ``game.status`` -- lifecycle: ``state`` in {started, won, draw} (won carries
  ``winner``). One stable type for the whole lifecycle so a monitor born at
  ``started`` is still alive to be settled at the terminal.
* ``game.move``   -- a stone placed: ``player``, ``cell``, and ``prev_player``
  (the player who made the immediately-preceding move in this game, or "none").
  ``prev_player`` is stamped from the true move order, which is what lets a
  single-event predicate decide strict alternation.
* ``game.ended``  -- the terminal: a game_id leaves the board. ``outcome`` in
  {won, draw, abandoned}. Settles the per-game monitors and frees state.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from behave_rv.events.event import Event

# Stable event-type identities (module-level constants: the emitted interface
# the stability analysis anchors on -- referenced by name, never computed).
STATUS_TYPE = "game.status"
MOVE_TYPE = "game.move"
ENDED_TYPE = "game.ended"

# game.status states
STARTED = "started"
WON = "won"
DRAW = "draw"
# game.ended outcomes
ABANDONED = "abandoned"

SOURCE = "tictactoe"
X = "X"
O = "O"
NONE = "none"

WIN_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # cols
    (0, 4, 8), (2, 4, 6),              # diagonals
)


class _Game:
    __slots__ = ("board", "turn", "last_mover", "over", "outcome", "winner")

    def __init__(self) -> None:
        self.board: list[Optional[str]] = [None] * 9
        self.turn: str = X                 # X always opens
        self.last_mover: Optional[str] = None
        self.over: bool = False
        self.outcome: Optional[str] = None
        self.winner: Optional[str] = None


class TicTacToeService:
    def __init__(self, emit: Callable[[Event], None],
                 clock: Callable[[], float] = time.time) -> None:
        self._emit = emit          # injected: live pushes to the queue+tap,
        self._clock = clock        # tests append to a list
        self._games: dict[str, _Game] = {}
        self._last_t: float = float("-inf")

    def _now(self) -> float:
        # Strictly increasing event times so two emissions whose order matters
        # (a winning move, then the "won" status) never share a timestamp and
        # get ordered content-canonically instead of causally.
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        return t

    # -- the single move emit site -----------------------------------------
    def _emit_move(self, game_id: str, player: str, cell: int, prev: str) -> None:
        self._emit(Event(MOVE_TYPE, self._now(), {"game_id": game_id},
                         {"player": player, "cell": cell, "prev_player": prev},
                         SOURCE))

    # -- lifecycle ----------------------------------------------------------
    def new_game(self, game_id: str) -> None:
        self._games[game_id] = _Game()
        self._emit(Event(STATUS_TYPE, self._now(), {"game_id": game_id},
                         {"state": STARTED}, SOURCE))

    def play(self, game_id: str, cell: int) -> bool:
        """Attempt a legal move for whoever's turn it is. Returns True if the
        move was legal and played, False otherwise (the correct game rejects
        out-of-turn / occupied / post-finish moves)."""
        game = self._games.get(game_id)
        if game is None or game.over:
            return False
        if not (0 <= cell < 9) or game.board[cell] is not None:
            return False
        self._place(game, game_id, game.turn, cell)
        return True

    def _place(self, game: _Game, game_id: str, player: str, cell: int) -> None:
        prev = game.last_mover or NONE
        self._emit_move(game_id, player, cell, prev)
        game.board[cell] = player
        game.last_mover = player
        game.turn = O if player == X else X
        if self._is_win(game.board, player):
            game.over = True
            game.outcome = WON
            game.winner = player
            self._emit(Event(STATUS_TYPE, self._now(), {"game_id": game_id},
                             {"state": WON, "winner": player}, SOURCE))
        elif all(c is not None for c in game.board):
            game.over = True
            game.outcome = DRAW
            self._emit(Event(STATUS_TYPE, self._now(), {"game_id": game_id},
                             {"state": DRAW}, SOURCE))

    def end_game(self, game_id: str, outcome: Optional[str] = None) -> None:
        """Retire a game_id: the terminal event. ``outcome`` defaults to the
        game's real outcome (won/draw) if it finished, else ``abandoned`` -- a
        game reset before it finished."""
        game = self._games.pop(game_id, None)
        if game is None:
            return
        final = outcome or (game.outcome if game.over else ABANDONED)
        self._emit(Event(ENDED_TYPE, self._now(), {"game_id": game_id},
                         {"outcome": final}, SOURCE))

    # -- raw tap for modelling corrupted events (never on the legal path) ----
    def force_move(self, game_id: str, player: str, cell: int) -> None:
        """Emit a raw move event WITHOUT the turn/occupancy/over guards.

        This models a corrupted or out-of-policy move reaching the monitor -- a
        double move by the same player, or a move after the game was won. It is
        used only by the fault-injecting demo, never by the browser's legal
        play path. ``prev_player`` is still stamped from the true last mover, so
        the injected event is a faithful-but-illegal record of the stream."""
        game = self._games.get(game_id)
        prev = (game.last_mover if game is not None else None) or NONE
        self._emit_move(game_id, player, cell, prev)
        if game is not None:
            game.last_mover = player

    @staticmethod
    def _is_win(board: list[Optional[str]], player: str) -> bool:
        return any(board[a] == board[b] == board[c] == player
                   for a, b, c in WIN_LINES)

    # -- read-only accessors for the UI ------------------------------------
    def snapshot(self, game_id: str) -> Optional[dict]:
        game = self._games.get(game_id)
        if game is None:
            return None
        return {
            "board": list(game.board),
            "turn": game.turn,
            "over": game.over,
            "outcome": game.outcome,
            "winner": game.winner,
            "last_mover": game.last_mover,
        }
