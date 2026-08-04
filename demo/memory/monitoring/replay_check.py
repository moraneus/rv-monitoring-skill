"""Deterministic verdict gate: scripted Memory traffic through the real game
service and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The traffic mixes healthy games (which must produce ZERO violations) with the
three seeded cheats, injected as CORRUPTED events straight into the stream -
exactly what the monitor exists to catch, and what the honest service never
emits:

  * a matched card re-flipped            -> rule 1
  * an attempt left hanging (no resolve) -> rule 2 (timer fires on the deadline)
  * activity after the game completed     -> rule 3 (post-terminal, fresh instance)

The post-completion cheat arrives AFTER the real game.completed terminal (the
terminal-windows rule): rule 3 is a self-contained `never`, so a fresh monitor
instance still violates - no false-green window.
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

from app.game import MemoryGame, FLIPPED, deal                  # noqa: E402
from steps import build_registry, load_policies                # noqa: E402

TERMINAL_TYPES = {"game.completed"}
EXPECTED = {
    ('a matched card is never flipped again', (('game_id', 'G1'),), 'satisfied'),
    ('a matched card is never flipped again', (('game_id', 'G2'),), 'violated'),
    ('a matched card is never flipped again', (('game_id', 'G4'),), 'satisfied'),
    ('a matched card is never flipped again', (('game_id', 'G4'),), 'violated'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a1'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a2'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a3'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a4'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a5'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a6'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a7'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a8'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G1-a9'), ('game_id', 'G1')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a1'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a2'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a3'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a4'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a5'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a6'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a7'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G2-a8'), ('game_id', 'G2')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G3-a1'), ('game_id', 'G3')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G3-hang'), ('game_id', 'G3')), 'violated'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a1'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a2'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a3'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a4'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a5'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a6'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a7'), ('game_id', 'G4')), 'satisfied'),
    ('an attempt resolves within 3 seconds', (('attempt_id', 'G4-a8'), ('game_id', 'G4')), 'satisfied'),
    ('nothing happens after the game is over', (('game_id', 'G1'),), 'satisfied'),
    ('nothing happens after the game is over', (('game_id', 'G2'),), 'satisfied'),
    ('nothing happens after the game is over', (('game_id', 'G4'),), 'satisfied'),
    ('nothing happens after the game is over', (('game_id', 'G4'),), 'violated'),
}


def settled_signature(v):
    """Order-independent identity for one settled verdict."""
    return (v.policy_id, tuple(sorted(v.entity_key.items())), v.verdict)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 0.25):
        self.now += dt


def _pairs(deck):
    """position pairs grouped by symbol: [[p1, p2], ...] (eight pairs)."""
    by_symbol: dict[str, list[int]] = {}
    for pos, symbol in enumerate(deck):
        by_symbol.setdefault(symbol, []).append(pos)
    return list(by_symbol.values())


def play_healthy(game: MemoryGame, clock: FakeClock, mismatches: int = 0) -> None:
    """Play a full honest game to completion, with `mismatches` deliberate
    wrong attempts first (each resolved by a flip-back well inside 3 seconds)."""
    game.start()
    clock.tick()
    pairs = _pairs(game.deck)
    for _ in range(mismatches):
        game.flip(pairs[0][0]); clock.tick()          # first card
        game.flip(pairs[1][0]); clock.tick(0.5)        # second card (mismatch)
        game.resolve_mismatch(); clock.tick()          # flip back @ +0.5s: in time
    for pair in pairs:
        game.flip(pair[0]); clock.tick()
        game.flip(pair[1]); clock.tick()               # match resolves instantly


def simulate_traffic(source: InProcessSource) -> None:
    clock = FakeClock()
    emit = source.emit

    # -- G1: a wholly healthy game (a described flow: zero violations) ------
    play_healthy(MemoryGame("G1", emit, clock, deal(seed=1)), clock, mismatches=1)

    # -- G2: a matched card re-flipped (rule 1) ----------------------------
    clock.tick(2.0)
    g2 = MemoryGame("G2", emit, clock, deal(seed=2))
    g2.start(); clock.tick()
    pair = _pairs(g2.deck)[0]
    g2.flip(pair[0]); clock.tick()
    g2.flip(pair[1]); clock.tick()                     # this pair is now matched
    # corrupted event: someone flips a card that is already part of a match.
    # slot='illegal' keeps it out of rule 2's second-card trigger.
    emit(Event(FLIPPED, clock(), {"game_id": "G2", "attempt_id": "G2-cheat",
                                  "position": pair[0]},
               {"slot": "illegal", "symbol": g2.deck[pair[0]],
                "already_matched": True, "after_completion": False}, "corrupted"))
    clock.tick()
    for p in _pairs(g2.deck)[1:]:                       # finish the game honestly
        g2.flip(p[0]); clock.tick()
        g2.flip(p[1]); clock.tick()

    # -- G3: an attempt left hanging (rule 2) ------------------------------
    clock.tick(2.0)
    g3 = MemoryGame("G3", emit, clock, deal(seed=3))
    g3.start(); clock.tick()
    p0 = _pairs(g3.deck)[0]
    g3.flip(p0[0]); clock.tick()
    g3.flip(p0[1]); clock.tick()                        # one healthy match
    # corrupted second-card flip that is NEVER resolved:
    hang_t = clock()
    emit(Event(FLIPPED, hang_t, {"game_id": "G3", "attempt_id": "G3-hang",
                                 "position": _pairs(g3.deck)[1][0]},
               {"slot": "second", "symbol": "?",
                "already_matched": False, "after_completion": False}, "corrupted"))
    # (no attempt.resolved for G3-hang; the 3s timer fires once later traffic
    #  advances event time past hang_t + 3 - the next game does exactly that.)

    # -- G4: activity after completion (rule 3, post-terminal) -------------
    clock.tick(4.0)                                     # > 3s: fires the G3 hang timer
    g4 = MemoryGame("G4", emit, clock, deal(seed=4))
    play_healthy(g4, clock, mismatches=0)               # runs to game.completed
    clock.tick(1.0)
    # corrupted flip arriving AFTER the terminal: also a matched-card re-flip,
    # so it trips rule 3 AND rule 1 on fresh post-terminal instances.
    emit(Event(FLIPPED, clock(), {"game_id": "G4", "attempt_id": "G4-post",
                                  "position": 0},
               {"slot": "illegal", "symbol": g4.deck[0],
                "already_matched": True, "after_completion": True}, "corrupted"))
    clock.tick()


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=0)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for verdict in verdicts:
        print(f"{verdict.verdict:9}  {str(verdict.entity_key):40}  {verdict.policy_id}")
    for verdict in violations:
        policy = by_id[verdict.policy_id]
        print()
        print(explain_verdict(verdict, policy.authored_scenario,
                              policy.failing_step_index))

    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s)")
    settled = {settled_signature(v) for v in verdicts
               if v.verdict in ("violated", "satisfied")}
    print()
    print(f"{len(verdicts)} verdicts, {len(violations)} violation(s), "
          f"{len(settled)} settled")
    if not EXPECTED:
        print("EXPECTED not pinned yet. Review the verdicts above, then set "
              "EXPECTED to this exact set:")
        for s in sorted(settled):
            print(f"    {s!r},")
        return 1
    missing = EXPECTED - settled
    unexpected = settled - EXPECTED
    for s in sorted(missing):
        print("MISSING (expected, did not occur):", s)
    for s in sorted(unexpected):
        print("UNEXPECTED (occurred, not pinned):", s)
    ok = not missing and not unexpected
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
