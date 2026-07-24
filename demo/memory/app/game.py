"""The Memory pairs game - the monitorable application.

A 4x4 board (8 pairs). The player flips two cards per attempt; a matched pair
stays face up, a mismatched pair flips back. When the eighth pair is found the
game is complete.

Instrumentation is ADDITIVE: every state transition emits an ``Event`` beside
the game logic, never reshaping it. The catalog's app side keys on these
``Event(...)`` construction sites, so each one is written inline with a
module-level event-type constant (see the rv skill's instrumentation
conventions).

Correlation keys, one entity family per key:
  * ``(game_id, position)`` - a single card within a game (rules about a card).
  * ``attempt_id``          - one two-card attempt (the resolve-in-time rule).
  * ``game_id``             - the whole game (the game-complete rule).

Attempt events deliberately carry ``game_id`` in the *payload*, not the
bindings, so they route only to attempt entities and never settle a game or a
card entity by mistake.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from behave_rv.events.event import Event

# --- event-type identities (contract; referenced by name at every emit) ------
GAME_START = "game.start"
GAME_ACTION = "game.action"       # heartbeat: one per player action in a game
GAME_COMPLETE = "game.complete"   # the eighth pair was found
CARD_FLIP = "card.flip"           # a card turned face up (a reveal)
CARD_MATCHED = "card.matched"     # a card became part of a found pair
ATTEMPT_PENDING = "attempt.pending"    # the second card is up; awaiting resolve
ATTEMPT_RESOLVED = "attempt.resolved"  # matched, or both flipped back

SOURCE = "memory-game"
PAIRS = 8                          # 4x4 board = 8 pairs
SYMBOLS = ["fox", "owl", "bee", "cat", "koi", "elk", "ram", "jay"]


class Clock:
    """A strictly-increasing event clock over a base time source.

    ``base()`` returns real (or fake) seconds; this wrapper guarantees every
    emission gets a distinct, ordered ``event_time`` so canonical order matches
    emission order for events that share a wall instant (the engine orders
    equal timestamps by content, which would otherwise misread ``before`` and
    the resolve-in-time deadline). The nudge is 0.1 ms - far below the 3 s
    deadline it must not distort.
    """

    def __init__(self, base):
        self._base = base
        self._last = 0.0

    def __call__(self) -> float:
        t = self._base()
        if t <= self._last:
            t = self._last + 1e-4
        self._last = t
        return t


@dataclass
class Card:
    position: int
    symbol: str
    matched: bool = False
    face_up: bool = False


@dataclass
class MemoryGame:
    """One game. Shares ``emit`` and ``clock`` with every other game so the
    whole system runs on one monotonic clock."""

    game_id: str
    emit: object                    # callable: Event -> None
    clock: object                   # callable: () -> float seconds
    order: list = field(default_factory=list)   # symbol per position, len 16
    cards: dict = field(default_factory=dict)   # position -> Card
    pending_first: int | None = None
    current_attempt: str | None = None
    attempt_seq: int = 0
    pending_mismatch: list = field(default_factory=list)
    pairs_found: int = 0
    complete: bool = False

    def __post_init__(self):
        for pos, symbol in enumerate(self.order):
            self.cards[pos] = Card(position=pos, symbol=symbol)

    # -- emission helper: build the Event at the site, one per call -----------
    def _fire(self, event: Event) -> None:
        self.emit(event)

    def start(self) -> None:
        self._fire(Event(GAME_START, self.clock(), {"game_id": self.game_id},
                         {"pairs": PAIRS}, SOURCE))

    def flip(self, position: int | None) -> dict:
        """Player action. ``position is None`` only clears a shown mismatch.

        Returns the board view for the UI. All monitorable facts are emitted as
        events; the return value is UI convenience, never read by the monitor.
        """
        if self.complete:
            return self.view("complete")

        # A shown mismatch clears when the next action begins (as in a real
        # memory game: the pair flips back when you touch the next card).
        if self.pending_mismatch:
            for p in self.pending_mismatch:
                self.cards[p].face_up = False
            self.pending_mismatch = []
            if position is None:
                return self.view("cleared")

        if position is None:
            return self.view("idle")

        card = self.cards[position]
        if card.matched or card.face_up:
            return self.view("ignored")     # not a new reveal; nothing to emit

        # Assign the attempt id on the first card of the pair.
        if self.pending_first is None:
            self.attempt_seq += 1
            self.current_attempt = f"{self.game_id}-a{self.attempt_seq}"

        card.face_up = True
        attempt_id = self.current_attempt
        self._fire(Event(CARD_FLIP, self.clock(),
                         {"game_id": self.game_id, "position": position},
                         {"symbol": card.symbol, "attempt_id": attempt_id},
                         SOURCE))
        self._fire(Event(GAME_ACTION, self.clock(), {"game_id": self.game_id},
                         {"kind": "flip"}, SOURCE))

        if self.pending_first is None:
            self.pending_first = position
            return self.view("first")

        first = self.pending_first
        second = position
        self.pending_first = None

        # The second card is up: the attempt is now awaiting resolution.
        self._fire(Event(ATTEMPT_PENDING, self.clock(), {"attempt_id": attempt_id},
                         {"game_id": self.game_id, "first": first,
                          "second": second}, SOURCE))

        matched = self.cards[first].symbol == self.cards[second].symbol
        if matched:
            for p in (first, second):
                self.cards[p].matched = True
                self._fire(Event(CARD_MATCHED, self.clock(),
                                 {"game_id": self.game_id, "position": p},
                                 {"symbol": self.cards[p].symbol,
                                  "attempt_id": attempt_id}, SOURCE))
            self.pairs_found += 1
            self._resolve(attempt_id, "matched")
            if self.pairs_found == PAIRS:
                self.complete = True
                self._fire(Event(GAME_COMPLETE, self.clock(),
                                 {"game_id": self.game_id},
                                 {"pairs": self.pairs_found}, SOURCE))
            return self.view("matched")

        self.pending_mismatch = [first, second]
        self._resolve(attempt_id, "mismatched")
        return self.view("mismatched")

    def _resolve(self, attempt_id: str, outcome: str) -> None:
        self._fire(Event(ATTEMPT_RESOLVED, self.clock(), {"attempt_id": attempt_id},
                         {"game_id": self.game_id, "outcome": outcome}, SOURCE))
        self._fire(Event(GAME_ACTION, self.clock(), {"game_id": self.game_id},
                         {"kind": "resolve"}, SOURCE))

    def view(self, phase: str) -> dict:
        return {
            "game_id": self.game_id,
            "phase": phase,
            "complete": self.complete,
            "pairs_found": self.pairs_found,
            "pairs_total": PAIRS,
            "cards": [
                {
                    "position": c.position,
                    "matched": c.matched,
                    # reveal the symbol only while the card is showing
                    "symbol": c.symbol if (c.face_up or c.matched) else None,
                }
                for c in (self.cards[i] for i in range(len(self.cards)))
            ],
        }


def new_order(seed: int | None = None) -> list:
    """A shuffled 16-card layout (8 symbols, twice each). Seedable for
    deterministic demo and replay traffic."""
    import random

    deck = SYMBOLS * 2
    random.Random(seed).shuffle(deck)
    return deck


def live_clock(start: float | None = None) -> Clock:
    """A service-relative wall clock: ``time.time() - start``, wrapped for
    strict monotonicity. Service-relative keeps dashboard and trace timestamps
    small and readable; any magnitude is correct on behave-rv >= 0.3.0."""
    origin = time.time() if start is None else start
    return Clock(lambda: time.time() - origin)
