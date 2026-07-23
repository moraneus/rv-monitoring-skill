"""Deterministic verdict gate: scripted booking traffic through the real
service and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

A FakeClock makes the run reproducible byte for byte (sleep just advances
time), so the same traffic always produces the same verdicts. ``clock.tick``
sits between every ordered action: with equal event times the engine orders
canonically (by content, not arrival), so actions whose order matters must
carry distinct timestamps.

EXPECTED pins the verdict/violation counts once green. Update it only for an
intended behaviour change, and say so in the report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # monitoring/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))      # project root

from app.booking_service import TERMINAL_TYPE, BookingService      # noqa: E402
from steps import build_registry, load_policies                   # noqa: E402

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.replay import ReplaySource, record_events  # noqa: E402
from behave_rv.verdict.explain import explain_verdict             # noqa: E402

TRACE = Path(__file__).parent / "traces" / "replay_check.jsonl"

# Pinned after the first green run. (verdicts, violations)
EXPECTED = {"verdicts": 43, "violations": 5}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(path: Path) -> None:
    clock = FakeClock()
    events: list = []
    svc = BookingService(events.append, clock=clock)

    # -- B-1001: fully healthy lifecycle -----------------------------------
    # reserve -> confirm -> check_in -> attended. Satisfies 02, 05, 06.
    svc.reserve("B-1001", "M-1", "C-1"); clock.tick(2)
    svc.confirm("B-1001", "M-1", "C-1"); clock.tick(2)
    svc.check_in("B-1001"); clock.tick(2)
    svc.mark_attended("B-1001"); clock.tick(2)

    # -- B-1002: waitlisted, promoted, confirmed IN TIME -------------------
    # promote -> confirm within 15s. Satisfies 04 (and 02, 05, 06).
    svc.reserve("B-1002", "M-2", "C-1"); clock.tick(1)
    svc.waitlist("B-1002"); clock.tick(1)
    svc.promote("B-1002"); clock.tick(5)          # 5s < 15s deadline
    svc.confirm("B-1002", "M-2", "C-1"); clock.tick(2)
    svc.check_in("B-1002"); clock.tick(2)
    svc.mark_attended("B-1002"); clock.tick(2)

    # -- B-1003: promotion times out ---------------------------------------
    # promote, then nothing for 20s. VIOLATES 04 (timer). 06 stays pending.
    svc.reserve("B-1003", "M-3", "C-2"); clock.tick(1)
    svc.waitlist("B-1003"); clock.tick(1)
    svc.promote("B-1003"); clock.tick(20)         # 20s > 15s deadline

    # -- B-1004: the nightmare - cancelled, then checked in ----------------
    # cancel is NOT a monitor-terminal, so the illegal check-in is still seen.
    # VIOLATES 01. (02 satisfied: it WAS confirmed. 06 satisfied: cancelled.)
    svc.reserve("B-1004", "M-4", "C-3"); clock.tick(2)
    svc.confirm("B-1004", "M-4", "C-3"); clock.tick(2)
    svc.cancel("B-1004"); clock.tick(2)
    svc.check_in("B-1004"); clock.tick(2)         # <- the anomaly

    # -- B-1005: checked in without ever being confirmed -------------------
    # VIOLATES 02.
    svc.reserve("B-1005", "M-5", "C-3"); clock.tick(2)
    svc.check_in("B-1005"); clock.tick(2)

    # -- B-1006: marked attended without a check-in ------------------------
    # sloppy front-desk marking. VIOLATES 05.
    svc.reserve("B-1006", "M-6", "C-4"); clock.tick(2)
    svc.confirm("B-1006", "M-6", "C-4"); clock.tick(2)
    svc.mark_attended("B-1006"); clock.tick(2)

    # -- M-7: confirmation while the member owes a balance -----------------
    # VIOLATES 03 (member-keyed).
    svc.incur_balance("M-7"); clock.tick(1)
    svc.reserve("B-1007", "M-7", "C-5"); clock.tick(1)
    svc.confirm("B-1007", "M-7", "C-5"); clock.tick(2)   # <- confirmed while owed

    # -- M-8: owed, then SETTLED, then confirmed ---------------------------
    # the until-window closes first, so this confirmation is allowed (03 not
    # violated) - shows the scoped prohibition lifting.
    svc.incur_balance("M-8"); clock.tick(1)
    svc.settle_balance("M-8"); clock.tick(1)
    svc.reserve("B-1008", "M-8", "C-5"); clock.tick(1)
    svc.confirm("B-1008", "M-8", "C-5"); clock.tick(2)

    record_events(path, events)


def main() -> int:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    simulate_traffic(TRACE)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types={TERMINAL_TYPE})
    verdicts = engine.run(ReplaySource(TRACE), emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    for v in sorted(verdicts, key=lambda v: (v.policy_id, str(v.entity_key))):
        key = ", ".join(f"{k}={val}" for k, val in v.entity_key.items())
        print(f"{v.verdict:9}  {key:22}  {v.policy_id}")

    for v in violations:
        policy = by_id[v.policy_id]
        print()
        print(explain_verdict(v, policy.authored_scenario, policy.failing_step_index))

    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s)")
    if EXPECTED["verdicts"] is None:
        print("EXPECTED not pinned yet: review the output above, then pin it.")
        return 1
    ok = (len(verdicts) == EXPECTED["verdicts"]
          and len(violations) == EXPECTED["violations"])
    if not ok:
        print(f"MISMATCH: expected {EXPECTED['verdicts']} verdicts / "
              f"{EXPECTED['violations']} violations")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
