"""The Memory-pairs game, instrumented for runtime verification.

This is the monitored application. It plays *honest* Memory: two cards flip
per attempt, matches stay up, the game ends when the last pair is found. The
only integration with behave-rv is a single injected ``emit`` called at each
observable state change - the business logic is never reshaped to be watched.

Event vocabulary (all events carry ``game_id``; attempt events also carry
``attempt_id`` so each attempt is its own monitored entity):

    game.started      a fresh board is dealt
    card.flipped      a card turns face up  (slot=first|second, symbol,
                      already_matched, after_completion)
    match.found       an attempt's two cards matched
    attempt.resolved  an attempt settled     (outcome=matched|mismatched)
    game.completed    the last pair was found  -- TERMINAL for game_id

The two history-stamped payload fields are what let single-entity policies
express per-occurrence rules (see monitoring/steps.py):
  * ``already_matched`` - was this card already part of a found pair when it
    was flipped?  (true only for an illegal re-flip)
  * ``after_completion`` - had the game already ended when this happened?
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from behave_rv.events.event import Event

# Event types are module-level constants, referenced by name: the stability
# analyzer resolves these and fingerprints the emit sites against them.
STARTED = "game.started"
FLIPPED = "card.flipped"
MATCHED = "match.found"
RESOLVED = "attempt.resolved"
COMPLETED = "game.completed"

SOURCE = "memory-game"

# Eight symbols, each dealt twice -> a 4x4 board of sixteen cards.
SYMBOLS = ["fox", "owl", "bee", "cat", "koi", "elk", "ram", "jay"]
BOARD_SIZE = 16
PAIRS = BOARD_SIZE // 2
FLIPBACK_DELAY = 1.1     # seconds a mismatched pair stays visible before resolving


def deal(seed: int | None = None) -> list[str]:
    """A shuffled 16-card board: each symbol appears at two positions."""
    deck = [SYMBOLS[i % len(SYMBOLS)] for i in range(BOARD_SIZE)]
    random.Random(seed).shuffle(deck)
    return deck


@dataclass
class MemoryGame:
    """One game of Memory, keyed by ``game_id``.

    ``emit`` and ``clock`` are injected so the identical object runs live
    (real clock, events into the engine) and under the scripted gate (fake
    clock, events into a list).
    """

    game_id: str
    emit: object                       # callable: Event -> None
    clock: object = time.time          # callable: () -> float
    deck: list[str] = field(default_factory=deal)

    matched: set = field(default_factory=set)     # positions locked face up
    face_up: list = field(default_factory=list)   # positions currently shown
    _attempt_no: int = 0
    _pending_pos: int | None = None               # first card awaiting a second
    _pending_attempt: str | None = None
    _await_mismatch: tuple | None = None          # (attempt_id, (a, b))
    completed: bool = False
    _last_t: float = 0.0

    # -- emission -----------------------------------------------------------
    def _stamp(self) -> float:
        """A strictly increasing event time: ordered actions never share a
        timestamp, so `within`/precedence read the true order."""
        t = max(self.clock(), self._last_t + 1e-3)
        self._last_t = t
        return t

    def start(self) -> None:
        self.emit(Event(STARTED, self._stamp(), {"game_id": self.game_id},
                        {"pairs": PAIRS, "after_completion": False}, SOURCE))

    def flip(self, position: int) -> None:
        """Play one legal flip. The caller (UI/driver) only ever passes a
        face-down, unmatched card of a game that is still running - the honest
        game never re-flips a matched card and never acts after completion.
        Corrupted events that do those things are injected into the stream
        directly in demo mode; catching them is the monitor's job."""
        symbol = self.deck[position]
        if self._pending_pos is None:
            self._open_attempt(position, symbol)
        else:
            self._close_attempt(position, symbol)

    def _open_attempt(self, position: int, symbol: str) -> None:
        self._attempt_no += 1
        attempt_id = f"{self.game_id}-a{self._attempt_no}"
        self._pending_pos = position
        self._pending_attempt = attempt_id
        self.face_up = [position]
        self.emit(Event(FLIPPED, self._stamp(),
                        {"game_id": self.game_id, "attempt_id": attempt_id,
                         "position": position},
                        {"slot": "first", "symbol": symbol,
                         "already_matched": False, "after_completion": False},
                        SOURCE))

    def _close_attempt(self, position: int, symbol: str) -> None:
        attempt_id = self._pending_attempt
        first = self._pending_pos
        self.face_up = [first, position]
        self.emit(Event(FLIPPED, self._stamp(),
                        {"game_id": self.game_id, "attempt_id": attempt_id,
                         "position": position},
                        {"slot": "second", "symbol": symbol,
                         "already_matched": False, "after_completion": False},
                        SOURCE))
        if self.deck[first] == symbol:
            self.matched.update((first, position))
            self.emit(Event(MATCHED, self._stamp(),
                            {"game_id": self.game_id},
                            {"position_a": first, "position_b": position,
                             "symbol": symbol, "after_completion": False},
                            SOURCE))
            self._pending_pos = self._pending_attempt = None
            self.face_up = []
            if len(self.matched) == BOARD_SIZE:
                self._complete()
            self._resolve(attempt_id, "matched")
        else:
            # The pair stays visible; the driver resolves it after the delay.
            self._await_mismatch = (attempt_id, (first, position))

    def resolve_mismatch(self) -> None:
        """Flip a mismatched pair back down and settle its attempt. Called by
        the driver after ``FLIPBACK_DELAY`` (live) or a clock tick (scripted)."""
        if self._await_mismatch is None:
            return
        attempt_id, _pair = self._await_mismatch
        self._resolve(attempt_id, "mismatched")
        self._await_mismatch = None
        self._pending_pos = self._pending_attempt = None
        self.face_up = []

    def _resolve(self, attempt_id: str, outcome: str) -> None:
        self.emit(Event(RESOLVED, self._stamp(),
                        {"game_id": self.game_id, "attempt_id": attempt_id},
                        {"outcome": outcome, "after_completion": False},
                        SOURCE))

    def _complete(self) -> None:
        self.completed = True
        self.emit(Event(COMPLETED, self._stamp(), {"game_id": self.game_id},
                        {"after_completion": False}, SOURCE))

    # -- read-only view for the browser -------------------------------------
    @property
    def awaiting(self) -> bool:
        return self._await_mismatch is not None

    def view(self) -> dict:
        """What the UI may see: symbols only for matched or face-up cards."""
        cards = []
        for pos in range(BOARD_SIZE):
            shown = pos in self.matched or pos in self.face_up
            cards.append({
                "position": pos,
                "symbol": self.deck[pos] if shown else None,
                "matched": pos in self.matched,
                "face_up": pos in self.face_up,
            })
        return {
            "game_id": self.game_id,
            "cards": cards,
            "matched_pairs": len(self.matched) // 2,
            "pairs": PAIRS,
            "completed": self.completed,
            "awaiting": self.awaiting,
            "busy": self._pending_pos is not None or self.awaiting,
        }
