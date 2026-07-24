"""Deterministic verdict gate: scripted traffic through the real game and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The traffic below drives, on a fake clock:
  * two full HEALTHY games - every rule must stay green (zero violations); a
    violation on a healthy flow would mean the rules jointly forbid normal
    play, a conflict to surface, never a count to pin;
  * four CHEATS injected as corrupted events, one per rule, so each rule is
    proven independently:
      A  re-flip a card that is already part of a found match   -> rule 1
      B  a game action after the game is complete               -> rule 3
      C  a second card flipped whose attempt never resolves     -> rule 2
      D  a card reported matched with no preceding flip         -> rule 4

Rule 3's entity (the game) has NO terminal event on purpose: game.complete is
left non-terminal so the prohibition stays armed after completion. Cheat B
arrives AFTER completion through the game's real completion timestamp and is
still caught - that is the check that the completed game is not falsely green.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.game import (                                          # noqa: E402
    MemoryGame, Clock, new_order,
    CARD_FLIP, CARD_MATCHED, GAME_ACTION, ATTEMPT_PENDING, SOURCE,
)
from steps import build_registry, load_policies                # noqa: E402

# game.complete is deliberately absent: it must NOT settle the game entity, or
# rule 3 would go falsely green at completion. attempt.resolved ends an attempt.
TERMINAL_TYPES = {"attempt.resolved"}
EXPECTED = {"verdicts": 137, "violations": 4}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def _pairs_sequence(order):
    """Click order that flips each matching pair together, in board order."""
    seen, seq = {}, []
    for pos, sym in enumerate(order):
        if sym in seen:
            seq += [seen.pop(sym), pos]
        else:
            seen[sym] = pos
    return seq


def _play(emit, clock, base, game_id, seed, pairs=None):
    """Play a game; ``pairs`` limits how many pairs are matched (None = full)."""
    order = new_order(seed)
    game = MemoryGame(game_id, emit, clock, order=order)
    game.start()
    clicks = _pairs_sequence(order)
    if pairs is not None:
        clicks = clicks[: pairs * 2]
    for pos in clicks:
        base.tick(0.05)
        game.flip(pos)
    return game


def simulate_traffic(emit) -> None:
    base = FakeClock()
    clock = Clock(base)

    # --- healthy games: must produce zero violations ------------------------
    _play(emit, clock, base, "G1", seed=1)          # full, completes
    _play(emit, clock, base, "G2", seed=2)          # full, completes

    # --- cheat A: re-flip a matched card (rule 1) ---------------------------
    base.tick(1.0)
    g3 = _play(emit, clock, base, "G3", seed=3, pairs=2)   # partial, not done
    matched_pos = next(i for i, c in g3.cards.items() if c.matched)
    base.tick(0.5)
    emit(Event(CARD_FLIP, clock(),
               {"game_id": "G3", "position": matched_pos},
               {"symbol": g3.cards[matched_pos].symbol,
                "attempt_id": "G3-cheat"}, SOURCE))

    # --- cheat B: a game action after completion (rule 3) -------------------
    # G1 completed long ago; this arrives at a later timestamp on the same
    # game entity, past the completion the real path emitted.
    base.tick(1.0)
    emit(Event(GAME_ACTION, clock(), {"game_id": "G1"},
               {"kind": "ghost"}, SOURCE))

    # --- cheat D: a match with no preceding flip (rule 4) -------------------
    # A card.matched for a card that was never flipped - a match appearing out
    # of nowhere. It is this card entity's first event, so "flipped before"
    # fails. (It also opens rule 1's scope, which stays pending: no later flip.)
    base.tick(1.0)
    emit(Event(CARD_MATCHED, clock(),
               {"game_id": "G6", "position": 0},
               {"symbol": "ghost", "attempt_id": "G6-cheat"}, SOURCE))

    # --- cheat C: an attempt that never resolves (rule 2) -------------------
    base.tick(1.0)
    emit(Event(ATTEMPT_PENDING, clock(), {"attempt_id": "G4-hang"},
               {"game_id": "G4", "first": 0, "second": 1}, SOURCE))
    base.tick(4.0)   # advance past the 3s deadline

    # --- trailing healthy game advances the clock horizon past the hang -----
    _play(emit, clock, base, "G5", seed=5)


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    # grace stays below the 3s within deadline (see the note in app/server.py);
    # scripted traffic is emitted in order, so a small window admits everything.
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=0.5)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    order = {"violated": 0, "satisfied": 1, "pending": 2}
    for verdict in sorted(verdicts, key=lambda v: (order[v.verdict], v.policy_id)):
        print(f"{verdict.verdict:9}  {verdict.entity_key}  {verdict.policy_id}")
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
        print(f"MISMATCH: expected {EXPECTED}, "
              f"got {{'verdicts': {len(verdicts)}, "
              f"'violations': {len(violations)}}}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
