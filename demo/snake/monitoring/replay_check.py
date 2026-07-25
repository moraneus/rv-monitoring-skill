"""Deterministic verdict gate: the scripted traffic through the real engine and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The traffic lives in ``app/traffic.py`` (shared with the live demo) so the gate
and the demo can never drift. Healthy games drive the real ``SnakeGame``;
faults are injected as corrupted stream events. The healthy flows must produce
ZERO violations; each fault must produce exactly its one expected violation.

No terminal event is declared for a game entity (see the note below), so the
post-"over" prohibitions stay armed and a post-over move/point is caught rather
than settled to a false green. Update EXPECTED only for intended behaviour
changes, and say so.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.traffic import play                                    # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

# A game entity has NO terminal event: "over" must NOT settle the entity, or the
# post-over prohibitions would go green the instant the game ends (a terminal
# settles a scoped `never` as satisfied). Entities are reclaimed by quiescence
# TTL instead - the practical guarantee window for rules 1a/1b.
TERMINAL_TYPES: set[str] = set()
EXPECTED = {"verdicts": 21, "violations": 4}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> list[tuple[str, str, str]]:
    clock = FakeClock()
    return play(emit, clock, clock.tick)


def main() -> int:
    source = InProcessSource()
    notes = simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    print("Scripted games:")
    for gid, what, rule in notes:
        print(f"  {gid:22}  {what}   [{rule}]")
    print()
    for verdict in verdicts:
        print(f"{verdict.verdict:9}  {str(verdict.entity_key):32}  {verdict.policy_id}")
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
