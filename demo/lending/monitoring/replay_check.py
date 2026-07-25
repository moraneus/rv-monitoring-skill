"""Deterministic verdict gate: scripted traffic through the real LendingService
and the compiled policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Every normal flow the user described is seeded here and MUST produce zero
violations (a violation on a healthy flow would mean the rules jointly forbid a
lifecycle the user relies on). Each rule also gets a fault seed so we prove the
monitor catches it. Ordered actions are separated by ``clock.tick`` so their
event times are distinct (equal times are ordered canonically, not by arrival).

Note on the deadline (rule 3): the ``within`` timer fires on absence. Under the
replay source there is no wall clock, so the deadline is driven by event time -
we advance the clock past 21s and emit a later, unrelated event so the engine's
time horizon crosses the deadline and the timer fires.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource   # noqa: E402
from behave_rv.verdict.explain import explain_verdict            # noqa: E402

from app.service import LendingService                           # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

# No terminal event is declared: reporting a loan lost must keep the loan's
# monitor armed so a later (buggy) renewal is still caught by rule 2. A terminal
# on "lost" would settle that prohibition as satisfied and hide the renewal. GC
# falls back to the quiescence TTL, set generously here.
QUIESCENCE_TTL = 3600.0
# Re-pinned when policies 04 (renew only after borrow) and 05 (returned never
# renewed) were adopted and their healthy+fault flows added to the traffic.
EXPECTED = {"verdicts": 45, "violations": 5}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    clock = FakeClock()
    svc = LendingService(emit, clock=clock)

    # --- Healthy flow 1: borrow then return, well inside the deadline. ---
    svc.borrow("L-borrow-return", "M-1", "C-1"); clock.tick(2)
    svc.return_("L-borrow-return"); clock.tick(2)

    # --- Healthy flow 2: borrow, renew, then return. ---
    svc.borrow("L-renew-return", "M-2", "C-2"); clock.tick(3)
    svc.renew("L-renew-return"); clock.tick(3)
    svc.return_("L-renew-return"); clock.tick(2)

    # --- Healthy flow 3: borrow then reported lost (a legitimate close). ---
    svc.borrow("L-lost", "M-3", "C-3"); clock.tick(4)
    svc.report_lost("L-lost"); clock.tick(2)

    # --- Fault seed, rule 1: a return with no prior borrow. ---
    svc.return_("L-return-first"); clock.tick(2)

    # --- Fault seed, rule 2: a renewal AFTER the copy was reported lost. The
    #     renew arrives well after the close, through the real service path. ---
    svc.borrow("L-lost-then-renew", "M-4", "C-4"); clock.tick(2)
    svc.report_lost("L-lost-then-renew"); clock.tick(5)
    svc.renew("L-lost-then-renew"); clock.tick(2)

    # --- Fault seed, policy 04 (renew only after borrow): a renewal with no
    #     prior borrow. ---
    svc.renew("L-renew-first"); clock.tick(2)

    # --- Fault seed, policy 05 (returned never renewed): a renewal AFTER the
    #     loan was returned, arriving through the real return path (the close),
    #     so the fault does not dodge the closing behaviour. ---
    svc.borrow("L-return-then-renew", "M-7", "C-7"); clock.tick(2)
    svc.return_("L-return-then-renew"); clock.tick(3)
    svc.renew("L-return-then-renew"); clock.tick(2)

    # --- Fault seed, rule 3: a loan borrowed and never settled. Advance past
    #     the 21s deadline so the timer fires; a later unrelated event moves the
    #     engine's event-time horizon across the deadline. ---
    svc.borrow("L-overdue", "M-5", "C-5")
    clock.tick(25)
    svc.borrow("L-horizon", "M-6", "C-6")   # unrelated; settled below in time
    clock.tick(1)
    svc.return_("L-horizon")


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, quiescence_ttl=QUIESCENCE_TTL)
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
