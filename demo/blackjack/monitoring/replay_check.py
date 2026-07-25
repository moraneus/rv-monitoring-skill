"""Deterministic verdict gate: scripted traffic through the real service and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The seeded flows live in ``app/scenarios.py`` (shared with the demo). Every
healthy hand runs through the real ``BlackjackTable`` and must produce zero
violations; the four cheats each produce exactly one violation (one per table
rule). The terminal-window probes deliberately add zero violations - they mark
the real detection window of the two scoped prohibitions (see the report).

Update EXPECTED only for intended behaviour changes, and say so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource   # noqa: E402
from behave_rv.verdict.explain import explain_verdict            # noqa: E402

from steps import build_registry, load_policies                  # noqa: E402
from app.scenarios import build_scripted_traffic                 # noqa: E402

TERMINAL_TYPES = {"hand.closed"}     # keep in sync with the application
# pinned 2026-07-25. Re-pinned same day for the intended addition of rule 5
# ("a losing hand is never paid out"): +1 policy, +2 seeded hands (cheat E and
# a rule-5 terminal-window probe). Violations 4 -> 6: cheat E (rule 5) and the
# rule-5 window probe's post-close payout, which rule 4 catches on a fresh
# post-terminal entity (rule 5's own window is confirmed - it does NOT flag it).
EXPECTED = {"verdicts": 61, "violations": 6}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def main() -> int:
    source = InProcessSource()
    clock = FakeClock()
    build_scripted_traffic(source.emit, clock)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=0.5)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for verdict in verdicts:
        print(f"{verdict.verdict:9}  {str(verdict.entity_key):18}  {verdict.policy_id}")
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
