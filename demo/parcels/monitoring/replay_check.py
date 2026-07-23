"""Deterministic verdict gate: scripted traffic through the real service and
policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Every seeded flow (healthy and faulty) runs with ``clock.tick`` between
ordered actions. Update EXPECTED only for intended behaviour changes, and say
so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource   # noqa: E402
from behave_rv.verdict.explain import explain_verdict            # noqa: E402

from app.parcel_service import ParcelService                    # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

# NOTE: delivery/return is a business end-of-life, but it is deliberately NOT
# configured as an engine terminal. Retiring a parcel at delivery would blind
# rule 2 ("once delivered, never re-routed") - the monitor must keep watching
# for a forbidden post-delivery reroute. Memory is reclaimed by quiescence TTL
# (live) instead; on replay the run simply drains and reports pending honestly.
EXPECTED = {"verdicts": 18, "violations": 3}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically through the real service."""
    clock = FakeClock()
    svc = ParcelService(emit, clock)

    # P-1 healthy: scanned, out for delivery, delivered in time -> all green.
    svc.register("P-1", "Berlin");        clock.tick()
    svc.hub_scan("P-1", "HUB-A");         clock.tick()
    svc.out_for_delivery("P-1");          clock.tick()
    svc.deliver("P-1");                   clock.tick()

    # P-2 healthy: scanned, out for delivery, returned in time -> all green.
    svc.register("P-2", "Munich");        clock.tick()
    svc.hub_scan("P-2", "HUB-B");         clock.tick()
    svc.out_for_delivery("P-2");          clock.tick()
    svc.return_to_sender("P-2");          clock.tick()

    # P-3 FAULT (policy 1): out for delivery with NO hub scan first.
    svc.register("P-3", "Hamburg");       clock.tick()
    svc.out_for_delivery("P-3");          clock.tick()
    svc.deliver("P-3");                   clock.tick()   # in time: policy 3 green

    # P-4 FAULT (policy 2): delivered, then re-routed afterwards.
    svc.register("P-4", "Cologne");       clock.tick()
    svc.hub_scan("P-4", "HUB-C");         clock.tick()
    svc.out_for_delivery("P-4");          clock.tick()
    svc.deliver("P-4");                   clock.tick()
    svc.route_to("P-4", "HUB-D");         clock.tick()

    # P-5 FAULT (policy 3): out for delivery, then never resolved in 12s.
    svc.register("P-5", "Bremen");        clock.tick()
    svc.hub_scan("P-5", "HUB-A");         clock.tick()
    svc.out_for_delivery("P-5")
    # advance event time past the 12s deadline so the timer fires on replay.
    clock.tick(20)
    svc.register("P-6", "Leipzig")        # a later event carries the clock past


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies)
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
