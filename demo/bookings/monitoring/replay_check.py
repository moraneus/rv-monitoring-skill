"""Deterministic replay gate for the class-bookings policies.

    python monitoring/replay_check.py        # exit 0 clean, exit 1 on drift

It simulates studio traffic with a fake clock (so the run is byte-for-byte
reproducible), records it to a trace, replays it through the same engine the
live monitor uses, and checks the verdicts against a PINNED expectation:

  * every healthy flow the owner described produces ZERO violations, and
  * every seeded fault produces exactly the one violation it is meant to.

If the actual violation set ever differs from the pin, the gate fails and
prints the difference - a red gate is the signal that code or policy moved.

Design notes worth knowing when reading the verdicts:

  * There is NO terminal event type (see app/booking_service.py). That is what
    keeps the "cancelled is never checked in" monitor alive to catch a
    post-cancellation check-in. The cost: `never` and `has happened` policies
    never settle inside a bounded replay - they report an honest `pending` for
    every booking. Pending is not a violation; the gate only pins violations.
  * The guarantee window for the post-cancellation check-in is the quiescence
    TTL (60s here, standing in for end-of-day). The B-CANCEL seed deliberately
    lands the check-in AFTER the cancellation, through the real service path,
    so the gate proves the rule catches exactly the owner's #1 worry.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # project root
sys.path.insert(0, str(Path(__file__).resolve().parent))          # monitoring/

from app.booking_service import BookingService                     # noqa: E402
from steps import build_registry, load_policies                    # noqa: E402

from behave_rv.engine.loop import Engine                           # noqa: E402
from behave_rv.events.sources.replay import ReplaySource, record_events  # noqa: E402
from behave_rv.verdict.explain import explain_verdict              # noqa: E402

QUIESCENCE_TTL = 60.0   # demo: keep watching each booking 60s past its last
                        # activity, standing in for the real "until end of day".


class FakeClock:
    """Deterministic time: tick() advances it; the same traffic always yields
    the same trace, so the gate is reproducible."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float):
        self.now += dt


# The one violation each seeded fault is meant to raise: (policy_id, booking_id).
EXPECTED_VIOLATIONS = {
    ("a cancelled booking is never checked in", "B-CANCEL"),
    ("a booking is only checked in after it was confirmed", "B-NOCONF"),
    ("a booking is only marked attended after check-in", "B-NOCHK"),
    ("a booking is never confirmed while the member owes money", "B-OWES"),
    ("a promoted booking is confirmed or cancelled within 15 seconds", "B-PROMO"),
    ("a booking never pushes its class over capacity", "B-C13"),
}


def simulate_traffic(path: Path) -> None:
    clock = FakeClock()
    events: list = []
    svc = BookingService(events.append, clock=clock)

    # tick between every ordered action: equal event times order canonically,
    # so actions whose order matters must carry distinct timestamps.

    # ---- healthy flows the owner described (expect ZERO violations) --------

    # B-1 straight through: reserve -> confirm -> check in -> attend
    svc.reserve("B-1")
    clock.tick(2.0); svc.confirm("B-1")
    clock.tick(3.0); svc.check_in("B-1")
    clock.tick(1.0); svc.mark_attended("B-1")

    # B-2 the waitlist path: waitlisted -> promoted -> confirmed in time -> ...
    clock.tick(1.0); svc.reserve("B-2")
    clock.tick(1.0); svc.waitlist("B-2")
    clock.tick(5.0); svc.promote("B-2")
    clock.tick(4.0); svc.confirm("B-2")            # 4s < 15s deadline: in time
    clock.tick(2.0); svc.check_in("B-2")
    clock.tick(1.0); svc.mark_attended("B-2")

    # B-3 a clean cancellation before check-in
    clock.tick(1.0); svc.reserve("B-3")
    clock.tick(2.0); svc.confirm("B-3")
    clock.tick(2.0); svc.cancel("B-3")

    # B-4 confirmed but a genuine no-show
    clock.tick(1.0); svc.reserve("B-4")
    clock.tick(2.0); svc.confirm("B-4")
    clock.tick(3.0); svc.mark_no_show("B-4")

    # ---- seeded faults (expect exactly one violation each) ----------------

    # B-CANCEL: the #1 nightmare - cancelled, then checked in anyway. The
    # check-in lands 3s AFTER the cancellation (well inside the 60s window),
    # through the real service path, and must be caught by policy 01.
    clock.tick(1.0); svc.reserve("B-CANCEL")
    clock.tick(2.0); svc.confirm("B-CANCEL")
    clock.tick(2.0); svc.cancel("B-CANCEL")
    clock.tick(3.0); svc.check_in("B-CANCEL")      # -> violates 01

    # B-NOCONF: checked in without ever being confirmed
    clock.tick(1.0); svc.reserve("B-NOCONF")
    clock.tick(2.0); svc.check_in("B-NOCONF")      # -> violates 02

    # B-NOCHK: marked attended without a check-in
    clock.tick(1.0); svc.reserve("B-NOCHK")
    clock.tick(2.0); svc.confirm("B-NOCHK")
    clock.tick(2.0); svc.mark_attended("B-NOCHK")  # -> violates 03

    # B-OWES: confirmed while the member still owed money
    clock.tick(1.0); svc.reserve("B-OWES")
    clock.tick(2.0); svc.confirm("B-OWES", balance_owed=True)   # -> violates 04

    # B-PROMO: promoted, then the member does nothing. The 15s timer must fire
    # on silence; later events (the capacity block below) advance event time
    # past the deadline so the timer resolves during replay.
    clock.tick(1.0); svc.reserve("B-PROMO")
    clock.tick(1.0); svc.waitlist("B-PROMO")
    clock.tick(1.0); svc.promote("B-PROMO")        # -> violates 05 by timeout
    clock.tick(20.0)                               # silence past the 15s deadline

    # Capacity: 13 members reserved into one class; the app's own counter trips
    # the cap marker on the 13th (B-C13), which policy 07 makes loud.
    for i in range(1, 14):
        clock.tick(0.5)
        svc.reserve(f"B-C{i:02d}", class_id="C-FULL")   # B-C13 -> violates 07

    record_events(path, events)


def main() -> int:
    trace = Path(__file__).parent / "traces" / "representative.jsonl"
    trace.parent.mkdir(exist_ok=True)
    simulate_traffic(trace)

    policies = load_policies(build_registry())
    engine = Engine(policies, terminal_event_types=set(),
                    grace=0.5, quiescence_ttl=QUIESCENCE_TTL)
    verdicts = engine.run(ReplaySource(trace), emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    actual = set()
    tally: Counter = Counter()
    for v in verdicts:
        tally[(v.policy_id, v.verdict)] += 1
        if v.verdict == "violated":
            actual.add((v.policy_id, v.entity_key["booking_id"]))

    # detail every violation, with the owner's own scenario as the counterexample
    print("=== violations ===")
    for v in verdicts:
        if v.verdict == "violated":
            print(f"\n[{v.entity_key['booking_id']}] {v.policy_id}")
            print(explain_verdict(v, by_id[v.policy_id].authored_scenario,
                                  by_id[v.policy_id].failing_step_index))

    # compact per-policy tally (pending is expected and honest under no-terminal)
    print("\n=== verdict tally (per policy) ===")
    for p in policies:
        counts = {k[1]: n for k, n in tally.items() if k[0] == p.policy_id}
        line = "  ".join(f"{verdict}={counts[verdict]}"
                         for verdict in ("violated", "satisfied", "pending")
                         if verdict in counts)
        print(f"  {p.policy_id:55}  {line or '-'}")

    missing = EXPECTED_VIOLATIONS - actual
    unexpected = actual - EXPECTED_VIOLATIONS
    print(f"\n{len(verdicts)} verdicts, {len(actual)} violation(s); "
          f"expected {len(EXPECTED_VIOLATIONS)}")
    if missing:
        print("MISSING expected violations:", sorted(missing))
    if unexpected:
        print("UNEXPECTED violations:", sorted(unexpected))
    ok = not missing and not unexpected
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
