"""Deterministic verdict gate: scripted traffic through the real service and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Healthy flows (a legal X win and a legal draw) must produce ZERO violations.
The fault seeds inject CORRUPTED events - events that bypass the service, as
a compromised or buggy producer would - to prove each law catches its
violation:

* law 1 (alternation): a move stamped player == prev_player (X twice running).
* law 2 (no move after decided): a move with after_finish "yes" injected
  AFTER the real game.over terminal - the mandated post-terminal seed, since
  game.over settles the game and a weaker (scoped) prohibition would show a
  false green here.
* law 3 (every game finishes): an in-progress game replaced by a new one, so
  its real closing behaviour is game.over "abandoned" - violated at that
  terminal.

Update EXPECTED only for intended behaviour changes, and say so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from steps import build_registry, load_policies, STATUS, OVER   # noqa: E402
from app.game import GameService                                # noqa: E402

TERMINAL_TYPES = {OVER}
EXPECTED = {"verdicts": 21, "violations": 3}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically through the real service."""
    clock = FakeClock()
    svc = GameService(emit, clock=clock)

    def play(cells):
        for c in cells:
            svc.play(c)
            clock.tick()

    def corrupt(gid, payload):
        """Inject an out-of-band game.status move (bypasses the service)."""
        emit(Event(STATUS, clock(), {"game_id": gid},
                   {"status": "move", **payload}, "corrupted"))
        clock.tick()

    X_WIN = [0, 3, 1, 4, 2]          # X takes the top row
    DRAW = [3, 5, 2, 1, 8, 4, 0, 6, 7]  # a verified cat's game

    # 1. healthy X win - all three laws satisfied
    svc.new_game(); clock.tick()
    play(X_WIN)

    # 2. healthy draw - all three laws satisfied
    svc.new_game(); clock.tick()
    play(DRAW)

    # 3. law 1 fault: a corrupted double move (X plays twice in a row) injected
    #    into an otherwise-legal game that still finishes.
    gid = svc.new_game(); clock.tick()
    svc.play(0); clock.tick()                          # legal X at 0
    corrupt(gid, {"player": "X", "prev_player": "X",   # <- illegal: X again
                  "after_finish": "no", "move_number": "99"})
    play([3, 1, 4, 2])                                 # legal play resumes, X wins

    # 4. law 2 fault: finish the game legally, then inject a move AFTER the
    #    real game.over terminal (the post-terminal seed).
    gid = svc.new_game(); clock.tick()
    play(X_WIN)                                         # game decided + game.over
    corrupt(gid, {"player": "O", "prev_player": "X",   # <- illegal: after decided
                  "after_finish": "yes", "move_number": "99"})

    # 5. law 3 fault: start a game, leave it in progress, replace it with a new
    #    one -> the abandoned game's terminal is game.over "abandoned".
    svc.new_game(); clock.tick()
    play([0, 3])                                       # in progress, not decided
    svc.new_game(); clock.tick()                       # abandons the previous game
    play(X_WIN)                                         # the replacement finishes


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
        print(f"MISMATCH: expected {EXPECTED}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
