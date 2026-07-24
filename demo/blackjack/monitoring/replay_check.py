"""Deterministic verdict gate: scripted traffic through the real service and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Healthy hands run through the REAL BlackjackGame (seeded deck) and must
produce zero violations. The cheats are injected as CORRUPTED raw events -
sequences the honest game would never emit - one per table rule, so the gate
proves each policy actually fires. One extra seed (a stray card arriving
AFTER the hand's real terminal ``hand.closed``) demonstrates the detection
window of the scoped prohibitions: a terminal settles them, so an occurrence
after close is NOT caught - the report names that window as a decision.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.game import (BlackjackGame, EVENT_CARD, EVENT_CLOSED,   # noqa: E402
                      EVENT_DEALT, EVENT_BUST, EVENT_PAYOUT,
                      EVENT_RESETTLED, EVENT_SETTLED, EVENT_STAND, SOURCE)
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {EVENT_CLOSED}          # hand.closed ends a round
# Pinned after a green run. Cheats A-D (rules 1-4) each violate once; rule 5
# (no double settlement) is caught both before close (cheatF) and after the
# real close (windowF/h4) - a self-contained `never` arms from entity birth,
# so the terminal does not hide the re-settlement marker.
EXPECTED = {"verdicts": 38, "violations": 6}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive healthy hands through the real game, then inject one corrupted
    sequence per table rule."""
    clock = FakeClock()

    # a small helper so injected raw events keep strictly increasing times
    last = {"t": 0.0}

    def inject(type_, hand_id, payload):
        t = clock()
        if t <= last["t"]:
            t = last["t"] + 1e-3
        last["t"] = t
        emit(Event(type_, t, {"hand_id": hand_id}, payload, SOURCE))

    # ---- healthy hands through the real service (seeded, deterministic) ----
    game = BlackjackGame(emit, clock=clock, rng=random.Random(7))
    for _ in range(3):
        game.new_hand()
        game.stand()
        clock.tick(1.0)
        last["t"] = clock()

    # ---- cheat A: a card dealt to the player AFTER the hand stands (rule 1)
    clock.tick(1.0)
    inject(EVENT_DEALT, "cheatA", {"bet": 10})
    inject(EVENT_CARD, "cheatA", {"to": "player", "rank": "9", "total": 9})
    inject(EVENT_STAND, "cheatA", {"player_total": 9})
    inject(EVENT_CARD, "cheatA", {"to": "player", "rank": "5", "total": 14})  # illegal
    inject(EVENT_SETTLED, "cheatA", {"outcome": "lose"})
    inject(EVENT_CLOSED, "cheatA", {})

    # ---- cheat B: a busted hand settled as a WIN (rule 2)
    clock.tick(1.0)
    inject(EVENT_DEALT, "cheatB", {"bet": 10})
    inject(EVENT_CARD, "cheatB", {"to": "player", "rank": "K", "total": 10})
    inject(EVENT_CARD, "cheatB", {"to": "player", "rank": "Q", "total": 20})
    inject(EVENT_CARD, "cheatB", {"to": "player", "rank": "8", "total": 28})
    inject(EVENT_BUST, "cheatB", {"who": "player", "total": 28})
    inject(EVENT_SETTLED, "cheatB", {"outcome": "win"})                      # illegal
    inject(EVENT_PAYOUT, "cheatB", {"amount": 20})
    inject(EVENT_CLOSED, "cheatB", {})

    # ---- cheat C: a hand that is dealt and never settled (rule 3, timeout)
    clock.tick(1.0)
    inject(EVENT_DEALT, "cheatC", {"bet": 10})
    inject(EVENT_CARD, "cheatC", {"to": "player", "rank": "7", "total": 7})
    # ... nobody ever finishes it. Advance event time past the 30s deadline so
    # the deadline matures on replay (event time drives `within` on replay).
    clock.tick(31.0)

    # ---- cheat D: a payout emitted BEFORE the settlement (rule 4)
    inject(EVENT_DEALT, "cheatD", {"bet": 10})
    inject(EVENT_CARD, "cheatD", {"to": "player", "rank": "10", "total": 10})
    inject(EVENT_STAND, "cheatD", {"player_total": 10})
    inject(EVENT_CARD, "cheatD", {"to": "dealer", "rank": "9", "total": 19})
    inject(EVENT_PAYOUT, "cheatD", {"amount": 20})                           # illegal
    inject(EVENT_SETTLED, "cheatD", {"outcome": "win"})
    inject(EVENT_CLOSED, "cheatD", {})

    # ---- window demo: a stray player card arriving AFTER the real terminal.
    # The hand stands, settles, and closes cleanly; the illegal card then lands
    # on the already-settled (reclaimed) entity, so rule 1 does NOT catch it.
    # This is the detection window (stand -> closed) made visible, not a bug.
    clock.tick(1.0)
    inject(EVENT_DEALT, "windowE", {"bet": 10})
    inject(EVENT_CARD, "windowE", {"to": "player", "rank": "10", "total": 10})
    inject(EVENT_STAND, "windowE", {"player_total": 10})
    inject(EVENT_CARD, "windowE", {"to": "dealer", "rank": "9", "total": 19})
    inject(EVENT_SETTLED, "windowE", {"outcome": "win"})
    inject(EVENT_PAYOUT, "windowE", {"amount": 20})
    inject(EVENT_CLOSED, "windowE", {})
    inject(EVENT_CARD, "windowE", {"to": "player", "rank": "3", "total": 13})  # after close

    # ---- cheat F: a settlement recomputed AFTER the hand already settled and
    # paid, before it closes (rule 5). The re-settlement marker `hand.resettled`
    # is what the game's guard emits on this leak path; injected here directly.
    clock.tick(1.0)
    inject(EVENT_DEALT, "cheatF", {"bet": 10})
    inject(EVENT_CARD, "cheatF", {"to": "player", "rank": "10", "total": 10})
    inject(EVENT_STAND, "cheatF", {"player_total": 10})
    inject(EVENT_CARD, "cheatF", {"to": "dealer", "rank": "9", "total": 19})
    inject(EVENT_SETTLED, "cheatF", {"outcome": "win"})
    inject(EVENT_PAYOUT, "cheatF", {"amount": 20})
    inject(EVENT_RESETTLED, "cheatF", {})                          # illegal re-settle
    inject(EVENT_CLOSED, "cheatF", {})

    # ---- mandatory post-terminal seed for the new scoped prohibition: drive a
    # real hand to its real closing behaviour, THEN a re-settlement arrives
    # after hand.closed. This checks whether the terminal hides the marker (see
    # the terminal-windows rule) - the report records the observed outcome.
    clock.tick(1.0)
    game.new_hand()
    game.stand()
    wf_id = game.state()["hand_id"]
    clock.tick(1.0)
    last["t"] = clock()
    inject(EVENT_RESETTLED, wf_id, {})                            # after real close


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for verdict in verdicts:
        print(f"{verdict.verdict:9}  {str(verdict.entity_key):22}  {verdict.policy_id}")
    for verdict in violations:
        policy = by_id[verdict.policy_id]
        print()
        print(explain_verdict(verdict, policy.authored_scenario,
                              policy.failing_step_index))

    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s)")
    if EXPECTED["verdicts"] is None:
        print("EXPECTED not pinned yet: review the output above, then set "
              "EXPECTED to lock this behaviour in.")
        return 1
    ok = (len(verdicts) == EXPECTED["verdicts"]
          and len(violations) == EXPECTED["violations"])
    if not ok:
        print(f"MISMATCH: expected {EXPECTED}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
