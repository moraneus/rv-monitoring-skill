"""Deterministic verdict gate: scripted traffic through the real ParcelService
and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Every seeded flow (healthy and faulty) runs with ``clock.tick`` between
ordered actions, so the same input yields the same trace and verdicts byte for
byte. The run also records that trace to ``traces/parcels.jsonl`` (with a
clock horizon) so ``catalog diff --trace`` and offline replay stay meaningful.
Update EXPECTED only for intended behaviour changes, and say so in the report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                       # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.events.sources.replay import record_events       # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.parcel_service import ParcelService                    # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

# No monitoring terminal: rule "a delivered parcel is never re-routed" needs
# the monitor to keep watching after delivery, so delivery is not terminal.
TERMINAL_TYPES: set[str] = set()
TRACE_PATH = Path(__file__).parent / "traces" / "parcels.jsonl"

EXPECTED = {"verdicts": 15, "violations": 3}   # pinned after first green run


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit, clock: FakeClock) -> None:
    """Drive every seeded flow deterministically."""
    svc = ParcelService(emit, clock=clock)

    def step(fn, *args):
        fn(*args)
        clock.tick()

    # P-1 healthy: scanned, out for delivery, delivered inside the window.
    step(svc.register, "P-1", "London")
    step(svc.hub_scan, "P-1", "HUB-A")
    step(svc.out_for_delivery, "P-1")
    step(svc.deliver, "P-1")

    # P-2 fault: out for delivery WITHOUT a hub scan (violates rule 1). Then
    # delivered in time, so its delivery-window policy is satisfied.
    step(svc.register, "P-2", "Paris")
    step(svc.out_for_delivery, "P-2")
    step(svc.deliver, "P-2")

    # P-3 fault: delivered, then RE-ROUTED (violates rule 2).
    step(svc.register, "P-3", "Berlin")
    step(svc.hub_scan, "P-3", "HUB-B")
    step(svc.out_for_delivery, "P-3")
    step(svc.deliver, "P-3")
    step(svc.route_to, "P-3", "HUB-C")

    # P-4 fault: out for delivery, then neither delivered nor returned before
    # the 12s window elapses (violates rule 3 by timer).
    step(svc.register, "P-4", "Rome")
    step(svc.hub_scan, "P-4", "HUB-A")
    step(svc.out_for_delivery, "P-4")
    clock.tick(15.0)                     # window blown, no finishing event

    # P-5 healthy: scanned, out for delivery, RETURNED inside the window.
    step(svc.register, "P-5", "Madrid")
    step(svc.hub_scan, "P-5", "HUB-B")
    step(svc.out_for_delivery, "P-5")
    step(svc.return_to_sender, "P-5")


def main() -> int:
    source = InProcessSource()
    recorded: list = []

    clock = FakeClock()
    simulate_traffic(lambda e: (recorded.append(e), source.emit(e)), clock)

    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    record_events(TRACE_PATH, recorded, horizon=clock())

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=0.0)
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
