"""Deterministic verdict gate: scripted booking traffic through the real
service and the real policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

``simulate_traffic`` drives every seeded flow - healthy paths plus one clean
violation per violating policy plus a deliberately stuck booking - with a
``FakeClock`` ticked between ordered actions so timestamps are distinct and
the trace is byte-for-byte reproducible. The same run records a representative
trace under traces/ for the ``catalog diff --trace`` liveness net.

Update EXPECTED only when behaviour intentionally changed, and say so.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.events.sources.replay import record_events       # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.booking_service import BookingService, TERMINAL_TYPE   # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {TERMINAL_TYPE}                 # booking.done: attended/no_show
QUIESCENCE_TTL = 3600.0                           # reclaim silent bookings (e.g.
#   a cancellation, which emits no terminal) after this long, in event seconds
GRACE = 0.5                                       # reorder window (event time)
TRACE_OUT = Path(__file__).parent / "traces" / "representative.jsonl"

EXPECTED = {"verdicts": 58, "violations": 6}      # pinned; see report


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically.

    One class session, member ids are illustrative. Each ``clock.tick`` gives
    the next action a distinct, strictly-later timestamp.
    """
    clock = FakeClock()
    svc = BookingService(emit, clock=clock)
    C = "spin-0700"                              # the class session for this run

    def step(fn, *args):
        clock.tick()
        fn(*args)

    # --- Healthy: waitlist -> promotion -> confirm -> check-in -> attended ----
    step(svc.waitlist, "B-100", "M-alice", C)
    step(svc.reserve, "B-101", "M-bob", C)       # healthy direct reserve

    # --- P2 violation: promoted but never confirmed or cancelled (times out) --
    step(svc.waitlist, "B-PROMO-LATE", "M-carol", C)
    step(svc.promote, "B-PROMO-LATE", "M-carol", C)   # deadline starts here

    step(svc.promote, "B-100", "M-alice", C)
    step(svc.confirm, "B-100", "M-alice", C)     # within 15s of its promotion
    step(svc.confirm, "B-101", "M-bob", C)

    # --- P4 violation: confirmed while the member still owes money -----------
    step(svc.reserve, "B-OWING", "M-dan", C)
    step(svc.confirm, "B-OWING", "M-dan", C, "owing", "none")

    # --- P5 violation: confirmed despite the app's duplicate flag ------------
    step(svc.reserve, "B-FLAGGED", "M-erin", C)
    step(svc.confirm, "B-FLAGGED", "M-erin", C, "clear", "duplicate")

    step(svc.check_in, "B-100", "M-alice", C)
    step(svc.check_in, "B-101", "M-bob", C)
    step(svc.check_in, "B-OWING", "M-dan", C)    # otherwise healthy
    step(svc.check_in, "B-FLAGGED", "M-erin", C)

    # --- P1 violation (the 3am nightmare): cancel, then still check in -------
    step(svc.reserve, "B-CANCEL-RETURN", "M-fred", C)
    step(svc.confirm, "B-CANCEL-RETURN", "M-fred", C)
    step(svc.cancel, "B-CANCEL-RETURN", "M-fred", C)   # emits no terminal

    # --- P3 violation: checked in without ever being confirmed --------------
    step(svc.reserve, "B-NOCONFIRM", "M-gina", C)
    step(svc.check_in, "B-NOCONFIRM", "M-gina", C)

    # --- P7 violation: marked attended with no check-in ---------------------
    step(svc.reserve, "B-ATTEND-NOCHECK", "M-hank", C)
    step(svc.confirm, "B-ATTEND-NOCHECK", "M-hank", C)
    step(svc.mark_attended, "B-ATTEND-NOCHECK", "M-hank", C)

    # --- P6 amber: a booking that never reaches an end state ----------------
    step(svc.reserve, "B-STUCK", "M-ivy", C)

    # --- Healthy bookings reach their end (terminal settles them green) ------
    step(svc.mark_attended, "B-100", "M-alice", C)
    step(svc.mark_attended, "B-101", "M-bob", C)
    step(svc.mark_attended, "B-OWING", "M-dan", C)
    step(svc.mark_attended, "B-FLAGGED", "M-erin", C)

    # The nightmare check-in arrives well after the cancellation, but before
    # the quiescence TTL reclaims the booking - so the monitor still sees it.
    step(svc.check_in, "B-CANCEL-RETURN", "M-fred", C)


def main() -> int:
    captured: list = []
    simulate_traffic(captured.append)

    TRACE_OUT.parent.mkdir(parents=True, exist_ok=True)
    record_events(TRACE_OUT, captured)           # feed catalog diff --trace

    source = InProcessSource()
    for event in captured:
        source.emit(event)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES,
                    quiescence_ttl=QUIESCENCE_TTL, grace=GRACE)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for verdict in verdicts:
        print(f"{verdict.verdict:9}  {str(verdict.entity_key):28}  {verdict.policy_id}")
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
