"""Deterministic scripted traffic shared by the demo and the replay gate.

Healthy hands run through the REAL ``BlackjackTable`` service. The cheats are
injected as *corrupted events* straight onto the emit stream - exactly what a
tampered or buggy game would put on the wire - so the monitor is shown
catching violations that bypass the game's own guards entirely.

``clock`` is a fake clock with ``.tick(dt)``; the caller pins timestamps by
ticking between ordered actions. One clock drives the whole timeline.
"""

from __future__ import annotations

from behave_rv.events.event import Event

from app.blackjack import (BlackjackTable, SOURCE, DEALT, STOOD, BUSTED,
                           SETTLED, PAYOUT, CLOSED, BET)

# hand_id -> (which rule it exercises, what to expect). For demo narration.
CHEATS = {
    "H-cheatA": ("rule 1", "a card is dealt AFTER the hand stood"),
    "H-cheatB": ("rule 2", "a busted hand is settled as a WIN"),
    "H-cheatC": ("rule 3", "the hand is dealt but never settled (nobody finishes)"),
    "H-cheatD": ("rule 4", "a payout is made BEFORE any settlement"),
    "H-cheatE": ("rule 5", "a hand settled as a LOSS is paid out anyway"),
}


def build_scripted_traffic(emit, clock) -> list[tuple[str, str]]:
    """Drive every seeded flow; return a narration log of (label, detail)."""
    table = BlackjackTable(emit, clock=clock)
    log: list[tuple[str, str]] = []

    def raw(ev_type, hand_id, payload):
        clock.tick(0.01)
        emit(Event(ev_type, clock(), {"hand_id": hand_id}, payload, SOURCE))

    # ---- HEALTHY hands, through the real service: expect ZERO violations ----
    clock.tick(1.0)
    table.new_hand(["KS", "9H", "QD", "7C", "2S"])
    clock.tick(0.5)
    table.stand()
    log.append(("healthy win", "player 20 stands, dealer draws to 18 -> win + payout"))

    clock.tick(1.0)
    table.new_hand(["10S", "10H", "9D", "9C"])
    clock.tick(0.5)
    table.stand()
    log.append(("healthy push", "19 vs 19 -> push, bet returned"))

    clock.tick(1.0)
    table.new_hand(["10D", "5S", "8H", "2C", "7D"])
    clock.tick(0.5)
    table.hit()
    log.append(("healthy bust", "player hits 10+8+7=25 -> busts -> settled lose"))

    clock.tick(1.0)
    table.new_hand(["7S", "10H", "10D", "10C"])
    clock.tick(0.5)
    table.stand()
    log.append(("healthy loss", "player 17 stands, dealer 20 -> settled lose"))

    # ---- CHEAT A (rule 1): a card dealt after the hand stood ----------------
    clock.tick(1.0)
    h = "H-cheatA"
    raw(DEALT, h, {"card": "KS", "total": 10, "to": "player"})
    raw(DEALT, h, {"card": "8H", "total": 18, "to": "player"})
    raw(STOOD, h, {"total": 18})
    raw(DEALT, h, {"card": "3D", "total": 21, "to": "player"})   # <-- violation
    raw(SETTLED, h, {"outcome": "win"})
    raw(PAYOUT, h, {"amount": 2 * BET})
    raw(CLOSED, h, {"outcome": "win"})
    log.append(("CHEAT A", "card dealt after stand -> rule 1 must violate"))

    # ---- CHEAT B (rule 2): a busted hand settled as a win -------------------
    clock.tick(1.0)
    h = "H-cheatB"
    raw(DEALT, h, {"card": "KS", "total": 10, "to": "player"})
    raw(DEALT, h, {"card": "9H", "total": 19, "to": "player"})
    raw(DEALT, h, {"card": "7D", "total": 26, "to": "player"})
    raw(BUSTED, h, {"total": 26})
    raw(SETTLED, h, {"outcome": "win"})                          # <-- violation
    raw(PAYOUT, h, {"amount": 2 * BET})
    raw(CLOSED, h, {"outcome": "win"})
    log.append(("CHEAT B", "busted hand settled as win -> rule 2 must violate"))

    # ---- CHEAT D (rule 4): a payout before any settlement -------------------
    clock.tick(1.0)
    h = "H-cheatD"
    raw(DEALT, h, {"card": "KS", "total": 10, "to": "player"})
    raw(DEALT, h, {"card": "KD", "total": 20, "to": "player"})
    raw(PAYOUT, h, {"amount": 2 * BET})                          # <-- violation
    raw(SETTLED, h, {"outcome": "win"})
    raw(CLOSED, h, {"outcome": "win"})
    log.append(("CHEAT D", "payout before settlement -> rule 4 must violate"))

    # ---- CHEAT E (rule 5): a hand settled as a loss, then paid out ----------
    # (rule 5's satisfied direction is already exercised by the two healthy
    # losing hands above - both settle "lose" and take no payout.)
    clock.tick(1.0)
    h = "H-cheatE"
    raw(DEALT, h, {"card": "KS", "total": 10, "to": "player"})
    raw(DEALT, h, {"card": "7H", "total": 17, "to": "player"})
    raw(STOOD, h, {"total": 17})
    raw(SETTLED, h, {"outcome": "lose"})
    raw(PAYOUT, h, {"amount": 2 * BET})                         # <-- violation
    raw(CLOSED, h, {"outcome": "lose"})
    log.append(("CHEAT E", "losing hand paid out -> rule 5 must violate"))

    # ---- CHEAT C (rule 3): a hand dealt that nobody ever finishes -----------
    clock.tick(1.0)
    h = "H-cheatC"
    raw(DEALT, h, {"card": "5S", "total": 5, "to": "player"})
    raw(DEALT, h, {"card": "6H", "total": 11, "to": "player"})
    raw(STOOD, h, {"total": 11})
    # no settlement, no close - the 30s deadline timer must fire on absence
    log.append(("CHEAT C", "hand never settled -> rule 3 must violate on timeout"))

    # advance event time past the 30s deadline so the absence timer fires,
    # and use the move to also probe the terminal windows (below).
    clock.tick(31.0)

    # ---- TERMINAL-WINDOW PROBES (honesty): a forbidden event AFTER the real
    # closing path. A hand.closed terminal settles its scoped prohibitions as
    # satisfied and frees the entity, so an occurrence arriving after close is
    # a fresh entity that never saw the scope open - NOT caught. These add
    # zero violations by design; they mark the real detection window.
    clock.tick(1.0)
    table.new_hand(["KS", "9H", "QD", "7C", "2S"])   # a real win hand -> closes
    stood_hid = table.hand_id
    clock.tick(0.5)
    table.stand()
    raw(DEALT, stood_hid, {"card": "3D", "total": 23, "to": "player"})  # after close: NOT caught
    log.append(("window probe 1",
                f"card dealt to {stood_hid} AFTER it closed -> NOT caught (rule 1 window)"))

    clock.tick(1.0)
    table.new_hand(["10D", "5S", "8H", "2C", "7D"])  # a real bust hand -> closes
    bust_hid = table.hand_id
    clock.tick(0.5)
    table.hit()
    raw(SETTLED, bust_hid, {"outcome": "win"})       # after close: NOT caught
    log.append(("window probe 2",
                f"{bust_hid} settled as win AFTER it closed -> NOT caught (rule 2 window)"))

    clock.tick(1.0)
    table.new_hand(["7S", "10H", "10D", "10C"])      # a real losing hand -> closes
    lose_hid = table.hand_id
    clock.tick(0.5)
    table.stand()
    raw(PAYOUT, lose_hid, {"amount": 2 * BET})       # after close: NOT caught
    log.append(("window probe 3",
                f"{lose_hid} paid AFTER it closed -> NOT caught (rule 5 window)"))

    return log
