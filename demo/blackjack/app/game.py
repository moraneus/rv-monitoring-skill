"""Blackjack game service (player vs dealer, one deck), instrumented for
behave-rv runtime verification.

The entity being monitored is a *hand*: one round, identified by ``hand_id``.
Every state transition of a hand emits an ``Event`` at the site, beside the
game logic - the instrumentation is additive and never reshapes play.

``emit`` and ``clock`` are injected through the constructor so the same code
runs live (real clock, events to the engine) and under scripted replay (fake
clock, events into a list) unchanged. Event types are module-level constants
referenced by name, so the stability analyzer can resolve them.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Optional

from behave_rv.events.event import Event

# --- the emitted interface: event types are constants, referenced by name ---
EVENT_DEALT = "hand.dealt"        # a new hand starts (lifecycle open)
EVENT_CARD = "hand.card"          # a card is dealt to player or dealer
EVENT_STAND = "hand.stand"        # the player stands (locks the player's hand)
EVENT_BUST = "hand.bust"          # player or dealer goes over 21
EVENT_SETTLED = "hand.settled"    # the round outcome is decided
EVENT_RESETTLED = "hand.resettled"  # a settlement attempt on an already-settled hand
EVENT_PAYOUT = "hand.payout"      # chips are paid to the player
EVENT_CLOSED = "hand.closed"      # the round is fully over (lifecycle terminal)

SOURCE = "blackjack"
BET = 10                          # fixed wager per hand, in chips
DEALER_STANDS_ON = 17             # dealer draws until reaching this total

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]


def _card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_total(cards: list[dict]) -> int:
    """Best blackjack total for a list of card dicts, aces soft where possible."""
    total = sum(_card_value(c["rank"]) for c in cards)
    aces = sum(1 for c in cards if c["rank"] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


class BlackjackGame:
    """One table. At most one hand is live at a time (single-player table)."""

    def __init__(self, emit: Callable[[Event], Any],
                 clock: Callable[[], float] = time.time,
                 rng: Optional[random.Random] = None):
        self._emit = emit
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_t = 0.0
        self._hand_seq = 0
        self._chips = 100
        self._deck: list[dict] = []
        self._hand: Optional[dict] = None   # the live round's state

    # -- ordered emission needs strictly increasing event time (see the
    #    instrumentation reference: equal times are ordered by content, so
    #    two ordered emissions must not share a timestamp) --
    def _tick(self) -> float:
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        return t

    def _shuffle(self) -> None:
        self._deck = [{"rank": r, "suit": s} for r in RANKS for s in SUITS]
        self._rng.shuffle(self._deck)

    def _draw(self) -> dict:
        if not self._deck:
            self._shuffle()
        return self._deck.pop()

    # ------------------------------------------------------------------ deal
    def new_hand(self) -> dict:
        self._shuffle()
        self._hand_seq += 1
        hand_id = f"h{self._hand_seq}"
        self._hand = {
            "hand_id": hand_id,
            "player": [],
            "dealer": [],
            "phase": "player",     # player | dealer | over
            "outcome": None,
        }
        self._emit(Event(EVENT_DEALT, self._tick(), {"hand_id": hand_id},
                         {"bet": BET}, SOURCE))
        # opening deal: two to the player, two to the dealer
        self._deal_to("player")
        self._deal_to("dealer")
        self._deal_to("player")
        self._deal_to("dealer")
        return self.state()

    def _deal_to(self, who: str) -> None:
        hand = self._hand
        card = self._draw()
        hand[who].append(card)
        total = hand_total(hand[who])
        self._emit(Event(EVENT_CARD, self._tick(), {"hand_id": hand["hand_id"]},
                         {"to": who, "rank": card["rank"], "total": total},
                         SOURCE))

    # ------------------------------------------------------------------- hit
    def hit(self) -> dict:
        hand = self._hand
        if hand is None or hand["phase"] != "player":
            return self.state()
        self._deal_to("player")
        if hand_total(hand["player"]) > 21:
            self._bust("player")
            self._settle("lose")     # a player bust loses immediately
        return self.state()

    # ----------------------------------------------------------------- stand
    def stand(self) -> dict:
        hand = self._hand
        if hand is None or hand["phase"] != "player":
            return self.state()
        # the player stands: from here the player's hand is locked
        self._emit(Event(EVENT_STAND, self._tick(), {"hand_id": hand["hand_id"]},
                         {"player_total": hand_total(hand["player"])}, SOURCE))
        hand["phase"] = "dealer"
        # the dealer now plays out (cards go to the dealer, never the player)
        while hand_total(hand["dealer"]) < DEALER_STANDS_ON:
            self._deal_to("dealer")
        dealer_total = hand_total(hand["dealer"])
        if dealer_total > 21:
            self._bust("dealer")
            self._settle("win")
        else:
            player_total = hand_total(hand["player"])
            if player_total > dealer_total:
                self._settle("win")
            elif player_total == dealer_total:
                self._settle("push")
            else:
                self._settle("lose")
        return self.state()

    # -------------------------------------------------------------- outcomes
    def _bust(self, who: str) -> None:
        hand = self._hand
        self._emit(Event(EVENT_BUST, self._tick(), {"hand_id": hand["hand_id"]},
                         {"who": who, "total": hand_total(hand[who])}, SOURCE))

    def _settle(self, outcome: str) -> None:
        hand = self._hand
        if hand["phase"] == "over":
            # re-settlement guard: the hand is already settled, so pay nothing
            # again and emit the marker the monitor watches. Honest play (hit
            # and stand guard on phase=="player") never reaches this branch.
            self._emit(Event(EVENT_RESETTLED, self._tick(),
                             {"hand_id": hand["hand_id"]}, {}, SOURCE))
            return
        hand["phase"] = "over"
        hand["outcome"] = outcome
        self._emit(Event(EVENT_SETTLED, self._tick(),
                         {"hand_id": hand["hand_id"]},
                         {"outcome": outcome}, SOURCE))
        # a payout happens only after settlement, and only when chips are owed
        if outcome == "win":
            self._pay(BET * 2)
        elif outcome == "push":
            self._pay(BET)
        self._close()

    def _pay(self, amount: int) -> None:
        hand = self._hand
        self._chips += amount
        self._emit(Event(EVENT_PAYOUT, self._tick(),
                         {"hand_id": hand["hand_id"]},
                         {"amount": amount}, SOURCE))

    def _close(self) -> None:
        hand = self._hand
        self._emit(Event(EVENT_CLOSED, self._tick(),
                         {"hand_id": hand["hand_id"]}, {}, SOURCE))

    # ------------------------------------------------------------------ view
    def state(self) -> dict:
        hand = self._hand
        if hand is None:
            return {"hand_id": None, "phase": "idle", "chips": self._chips}
        # while the player is acting, keep the dealer's hole card face down
        reveal_dealer = hand["phase"] != "player"
        dealer_cards = hand["dealer"] if reveal_dealer else hand["dealer"][:1]
        return {
            "hand_id": hand["hand_id"],
            "phase": hand["phase"],
            "outcome": hand["outcome"],
            "chips": self._chips,
            "bet": BET,
            "player": hand["player"],
            "player_total": hand_total(hand["player"]),
            "dealer": dealer_cards,
            "dealer_total": (hand_total(hand["dealer"]) if reveal_dealer
                             else hand_total(hand["dealer"][:1])),
            "dealer_hidden": not reveal_dealer,
        }
