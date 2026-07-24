"""Deterministic verdict gate: scripted traffic through the real service and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Maintain ``simulate_traffic`` alongside the application: every seeded flow
(healthy and faulty) with ``clock.tick`` between ordered actions. Include
EVERY normal flow the user described - those must produce zero violations;
a violation on a described healthy flow means the policies jointly forbid
a lifecycle the user relies on, which is a rule conflict to surface, never
a count to pin. Update EXPECTED only for intended behaviour changes, and
say so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                       # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {"__DOMAIN__.done"}     # keep in sync with the application
EXPECTED = {"verdicts": None, "violations": None}   # pin after first green run


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically. FILL ME per application."""
    clock = FakeClock()
    _ = (emit, clock)
    raise NotImplementedError("script the application's seeded flows here")


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
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
