"""Single-deck Blackjack (player vs dealer), instrumented for behave-rv.

The game logic is ordinary; the runtime-verification surface is purely
*additive*: at every state transition we construct an ``Event(...)`` directly
at the site, using module-level string constants for the event type and dict
literals for the bindings and payload. That syntactic shape is what the
behave-rv stability analyzer keys on - see the rv skill's instrumentation
reference. Nothing here is reshaped to be observable.

``emit`` and ``clock`` are injected through the constructor so the exact same
class runs live (real clock, events into the engine) and under scripted replay
(fake clock, events into a list) with no change.
"""

from __future__ import annotations

import random
import time
from typing import Callable, Optional

from behave_rv.events.event import Event

# --- the monitorable event vocabulary (stable identities, referenced by name) -
DEALT = "hand.dealt"        # a card is added to the player's hand
STOOD = "hand.stood"        # the player stands
BUSTED = "hand.busted"      # the player's total went over 21
SETTLED = "hand.settled"    # the hand's outcome is decided (win / lose / push)
PAYOUT = "hand.payout"      # chips are paid to the player
CLOSED = "hand.closed"      # the round is fully over (terminal: frees the entity)

SOURCE = "blackjack-table"
BET = 10

RANK_VALUE = {
    "A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10,
}
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]


def rank_of(card: str) -> str:
    return card[:-1]


def hand_total(cards: list[str]) -> int:
    """Best blackjack total: aces count 11 until that would bust, then 1."""
    total = sum(RANK_VALUE[rank_of(c)] for c in cards)
    aces = sum(1 for c in cards if rank_of(c) == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def fresh_deck() -> list[str]:
    return [rank + suit for suit in SUITS for rank in RANKS]


class BlackjackTable:
    """One player vs the dealer, single deck. State transitions emit events."""

    def __init__(self, emit: Callable[[Event], None],
                 clock: Callable[[], float] = time.time,
                 rng: Optional[random.Random] = None):
        self._emit = emit
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_t = 0.0
        self._count = 0
        self.hand_id = ""
        self.player: list[str] = []
        self.dealer: list[str] = []
        self.status = "idle"
        self.outcome = ""
        self._deck: list[str] = []

    # strictly increasing event times: ordered emissions must not share a
    # timestamp (behave-rv orders equal times canonically, which would misread
    # precedence). One clock, nudged forward by a millisecond when needed.
    def _now(self) -> float:
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        return t

    def new_hand(self, deck: Optional[list[str]] = None) -> dict:
        self._count += 1
        self.hand_id = f"H-{self._count}"
        self._deck = list(deck) if deck is not None else fresh_deck()
        if deck is None:
            self._rng.shuffle(self._deck)
        self.player = []
        self.dealer = []
        self.outcome = ""
        self.status = "playing"
        self._deal_to_player()
        self.dealer.append(self._deck.pop(0))
        self._deal_to_player()
        self.dealer.append(self._deck.pop(0))
        return self.state()

    def _deal_to_player(self) -> None:
        card = self._deck.pop(0)
        self.player.append(card)
        self._emit(Event(DEALT, self._now(), {"hand_id": self.hand_id},
                         {"card": card, "total": hand_total(self.player),
                          "to": "player"}, SOURCE))

    def hit(self) -> dict:
        if self.status != "playing":
            return self.state()
        self._deal_to_player()
        if hand_total(self.player) > 21:
            self.status = "busted"
            self._emit(Event(BUSTED, self._now(), {"hand_id": self.hand_id},
                             {"total": hand_total(self.player)}, SOURCE))
            self._settle("lose")
            self._close()
        return self.state()

    def stand(self) -> dict:
        if self.status != "playing":
            return self.state()
        self.status = "stood"
        self._emit(Event(STOOD, self._now(), {"hand_id": self.hand_id},
                         {"total": hand_total(self.player)}, SOURCE))
        while hand_total(self.dealer) < 17:
            self.dealer.append(self._deck.pop(0))
        player_total = hand_total(self.player)
        dealer_total = hand_total(self.dealer)
        if dealer_total > 21 or player_total > dealer_total:
            outcome = "win"
        elif player_total < dealer_total:
            outcome = "lose"
        else:
            outcome = "push"
        self._settle(outcome)
        if outcome == "win":
            self._pay(BET * 2)
        elif outcome == "push":
            self._pay(BET)
        self._close()
        return self.state()

    def _settle(self, outcome: str) -> None:
        self.status = "settled"
        self.outcome = outcome
        self._emit(Event(SETTLED, self._now(), {"hand_id": self.hand_id},
                         {"outcome": outcome}, SOURCE))

    def _pay(self, amount: int) -> None:
        self._emit(Event(PAYOUT, self._now(), {"hand_id": self.hand_id},
                         {"amount": amount}, SOURCE))

    def _close(self) -> None:
        self._emit(Event(CLOSED, self._now(), {"hand_id": self.hand_id},
                         {"outcome": self.outcome}, SOURCE))

    def state(self) -> dict:
        dealer_view = list(self.dealer)
        # hide the dealer hole card while the player is still acting
        if self.status in ("playing",):
            dealer_view = self.dealer[:1] + ["??"] * (len(self.dealer) - 1)
        return {
            "hand_id": self.hand_id,
            "status": self.status,
            "outcome": self.outcome,
            "player": list(self.player),
            "player_total": hand_total(self.player),
            "dealer": dealer_view,
            "dealer_total": (hand_total(self.dealer)
                             if self.status not in ("playing",) else None),
            "bet": BET,
        }
