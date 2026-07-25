"""Replay a recorded event trace through the committed policies.

    python replay_trace.py [monitoring/traces/live_session.jsonl]

Feeds a trace recorded by the live demo (or any behave-rv .jsonl trace) back
through the SAME policies and engine and prints the verdicts with rendered
explanations. This is how you re-examine a past session, or test a new policy
against traffic you already captured, without touching live parcels. The
trace's trailing clock-horizon marker makes wall-fired deadline verdicts
(rule 3) reproduce here exactly as they fired live.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))

from behave_rv.engine.loop import Engine                       # noqa: E402
from behave_rv.events.sources.replay import ReplaySource       # noqa: E402
from behave_rv.verdict.explain import explain_verdict          # noqa: E402

from steps import build_registry, load_policies                # noqa: E402

DEFAULT_TRACE = "monitoring/traces/live_session.jsonl"


def main() -> int:
    trace = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TRACE

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, quiescence_ttl=120.0, grace=0.0)
    verdicts = engine.run(ReplaySource(trace), emit_pending=True)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
