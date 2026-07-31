"""Deterministic verdict gate: scripted traffic through the real service and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Maintain ``simulate_traffic`` alongside the application: every seeded flow
(healthy and faulty) with ``clock.tick`` between ordered actions. Drive EVERY
exposed operation at least once - an operation the traffic never calls is one
this gate can never check, so a bug in it slips through green (run
``catalog coverage`` to see which emitted events and fields no traffic or
policy exercises). Include EVERY normal flow the user described - those must
produce zero violations;
a violation on a described healthy flow means the policies jointly forbid
a lifecycle the user relies on, which is a rule conflict to surface, never
a count to pin. For every scoped prohibition on an entity with a terminal
event, include a fault that arrives AFTER the real closing behaviour: a
terminal settles prohibitions as satisfied, so a seed that dodges it can
"prove" a rule whose real detection window is milliseconds (see the
terminal-windows rule in the policy-authoring reference).

Pin the exact SET of settled ``(policy, entity, verdict)`` verdicts, never the
totals: two compensating bugs can keep the counts identical while WHICH
verdicts occur changes (an expected violation vanishes just as an unexpected
one appears), so a count gate goes green on broken code. Update EXPECTED only
for intended behaviour changes, and say so in the commit.
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

# The exact set of settled (violated/satisfied) verdicts this traffic must
# produce, one entry per verdict: (policy_id, entity, verdict). Pin it from the
# bootstrap output after a green run. Never pin counts - they hide compensating
# bugs (an expected violation lost while an unexpected one appears).
EXPECTED: set = set()


def settled_signature(v):
    """Order-independent identity for one settled verdict."""
    return (v.policy_id, tuple(sorted(v.entity_key.items())), v.verdict)


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

    settled = {settled_signature(v) for v in verdicts
               if v.verdict in ("violated", "satisfied")}
    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s), "
          f"{len(settled)} settled")
    if not EXPECTED:
        print("EXPECTED not pinned yet. Review the verdicts above, then set "
              "EXPECTED to this exact set:")
        for s in sorted(settled):
            print(f"    {s!r},")
        return 1
    missing = EXPECTED - settled          # a pinned verdict that did not occur
    unexpected = settled - EXPECTED       # a verdict that occurred but is not pinned
    for s in sorted(missing):
        print("MISSING (expected, did not occur):", s)
    for s in sorted(unexpected):
        print("UNEXPECTED (occurred, not pinned):", s)
    ok = not missing and not unexpected
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
