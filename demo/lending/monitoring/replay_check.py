"""Deterministic verdict gate: scripted traffic through the real
LendingService and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

``simulate_traffic`` drives the real service with a fake clock, ticking
between ordered actions. Every seeded flow (healthy and faulty) is here, so
the replay says what *did* happen - the static catalog diff only says what
*may* be affected. Update EXPECTED only for intended behaviour changes, and
say so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.lending_service import LendingService, TERMINAL_TYPE   # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {TERMINAL_TYPE}
WINDOW = 21.0  # the demo deadline, seconds (21 days -> 21 seconds)

# Pinned after a green run (see the verdict list the script prints). Five
# policies now, exercised across the seeded loans:
#   - L-1 healthy: all applicable policies SATISFIED
#   - L-2 abandoned after borrow: settle-within-window VIOLATED (timer)
#   - L-3 lost then illegally renewed: never-renew-after-lost VIOLATED, and
#     the unsettled illegal renewal -> renewal-window VIOLATED
#   - L-4 return with no checkout: return-after-borrow VIOLATED
#   - L-6 renew with no checkout: renew-after-borrow VIOLATED, and the
#     unsettled renewal -> renewal-window VIOLATED
#   - L-7 fine guard: M-5 owes -> renew refused -> pays -> renew allowed ->
#     return. All L-7 loan policies satisfied; the fines-freeze-renewals policy
#     stays pending for M-5 (the guard holds, so it never fires)
#   - L-9 sentinel borrow+return: clean, advances the clock so the timers fire
# 33 verdicts total (16 satisfied, 6 violated, 11 honest pending) across the
# six policies. The three member entities (M-5, M-7, M-9 - anyone with a
# member.renewal or fine event) each get a pending fines-freeze verdict; it is
# a tripwire that only fires if a renewal ever slips through an owed window.
EXPECTED = {"verdicts": 33, "violations": 6}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically."""
    clock = FakeClock()
    svc = LendingService(emit, clock=clock)

    # L-1 healthy: borrowed, renewed inside the window, returned inside it.
    # The renewal is settled by the return, so the renewal-window policy is
    # satisfied and the renewal-after-borrow policy is satisfied.
    svc.borrow("L-1", member_id="M-7", copy_id="C-100")
    clock.tick(5)
    svc.renew("L-1")
    clock.tick(4)
    svc.return_loan("L-1")

    # L-2 abandoned: borrowed and never acted on -> deadline must fire.
    clock.tick(1)
    svc.borrow("L-2", member_id="M-3", copy_id="C-200")
    clock.tick(WINDOW + 1)   # push event time past the 21s deadline

    # L-3 lost then renewed: the renew path forgot the loan was frozen. The
    # illegal renewal violates never-renew-after-lost, and - being a renewal
    # that is itself never settled - also violates the renewal-window policy.
    svc.borrow("L-3", member_id="M-9", copy_id="C-300")
    clock.tick(2)
    svc.report_lost("L-3")
    clock.tick(2)
    svc.renew("L-3")         # forbidden: renew after lost

    # L-4 a return with no matching checkout (a mis-scanned reshelve).
    clock.tick(1)
    svc.return_loan("L-4")

    # L-6 a renewal of a loan that was never borrowed (a duplicated or
    # mis-scanned record): violates renewal-after-borrow, and the unsettled
    # renewal also violates the renewal-window policy.
    clock.tick(3)
    svc.renew("L-6")

    # L-7 exercises the fine guard end to end. Member M-5 owes, so the renewal
    # is REFUSED (nothing emitted); once paid off the renewal goes through and
    # the loan returns in time. Because the guard blocks the renewal during the
    # owed window, the fines-freeze-renewals policy is never violated - it is a
    # tripwire that only fires if the guard is bypassed. Driving the real
    # service, it correctly stays out of violation for M-5.
    clock.tick(2)
    svc.borrow("L-7", member_id="M-5", copy_id="C-700")
    clock.tick(1)
    svc.record_fine("M-5", amount=2.0)
    clock.tick(1)
    svc.renew("L-7")            # refused: M-5 owes -> no event
    clock.tick(1)
    svc.pay_fine("M-5")
    clock.tick(1)
    svc.renew("L-7")           # now allowed
    clock.tick(1)
    svc.return_loan("L-7")

    # Sentinel flow, far in the future: a clean borrow+return whose event
    # times advance the clock past every earlier renewal deadline, so the
    # absence-based renewal-window timers (L-3, L-6) fire deterministically
    # in replay. It resolves cleanly and adds no violations.
    clock.tick(60)
    svc.borrow("L-9", member_id="M-1", copy_id="C-900")
    clock.tick(1)
    svc.return_loan("L-9")


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
