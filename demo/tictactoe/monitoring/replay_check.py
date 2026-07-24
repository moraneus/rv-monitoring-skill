"""Deterministic verdict gate: scripted traffic through the real service and
the real policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The scripted traffic (``demo_script.run_script``) plays two healthy games to
completion (zero violations -- the jointly-satisfiable check) and injects the
four faults the game's laws forbid. The post-finish move fault arrives BEFORE
its game's terminal, because a terminal settles the prohibition (the
terminal-windows rule); a seed that dodged the terminal would prove nothing.
The orphan-move fault (g6) exercises the "no orphan moves" rule and, honestly,
also leaves g6's move-observing lifecycle policies pending -- a move with no
lifecycle is a degenerate entity.

Update EXPECTED only for intended behaviour changes, and say so in the report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # monitoring/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))      # project root

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource    # noqa: E402
from behave_rv.verdict.explain import explain_verdict             # noqa: E402

from app.game_service import TicTacToeService, ENDED_TYPE         # noqa: E402
from demo_script import Clock, run_script                         # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402

TERMINAL_TYPES = {ENDED_TYPE}
# Re-pinned 2026-07-25 for the intended addition of the "no orphan moves" policy
# and the g6 orphan-move fault: +5 satisfied (g1-g5), +1 violated (g6), +2 g6
# pendings on the lifecycle policies. Was {15, 4}.
EXPECTED = {"verdicts": 23, "violations": 5}


def main() -> int:
    source = InProcessSource()
    clock = Clock()
    service = TicTacToeService(source.emit, clock=clock)
    run_script(service, clock)

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
