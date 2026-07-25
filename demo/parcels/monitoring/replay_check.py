"""Deterministic verdict gate: scripted traffic through the REAL ParcelService
and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Every flow is driven through the real service methods (never by hand-crafting
events), with a fake clock ticked between ordered actions so event times are
distinct and deadlines are exercised. Healthy flows must produce zero
violations; each fault flow proves exactly one rule fires.

No terminal event is configured: ``delivered``/``returned`` intentionally do
NOT retire the entity, so rule 2 ("once delivered, never re-routed") stays
armed and catches a reroute that arrives AFTER delivery (fault B). A terminal
on delivery would settle rule 2 as satisfied and make that reroute invisible.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                       # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.parcel_service import ParcelService                    # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

# Finished parcels are reclaimed by quiescence, not by a terminal event
# (see the module docstring and the monitoring report).
TERMINAL_TYPES: set[str] = set()
QUIESCENCE_TTL = 30.0
DEADLINE = 12.0

EXPECTED = {"verdicts": 13, "violations": 3}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow through the real service, deterministically."""
    clock = FakeClock()
    svc = ParcelService(emit=emit, clock=clock)

    # --- Healthy flow 1: scanned, dispatched, delivered in time -----------
    svc.register("H1", "12 Oak St")
    clock.tick()
    svc.hub_scan("H1", "hub-a")
    clock.tick()
    svc.out_for_delivery("H1")
    clock.tick(5)                      # delivered 5s after dispatch (< 12s)
    svc.deliver("H1")

    # --- Healthy flow 2: scanned, dispatched, returned in time ------------
    clock.tick()
    svc.register("H2", "9 Elm Ave")
    clock.tick()
    svc.hub_scan("H2", "hub-b")
    clock.tick()
    svc.out_for_delivery("H2")
    clock.tick(4)                      # returned 4s after dispatch (< 12s)
    svc.return_to_sender("H2")

    # --- Fault A: dispatched with NO hub scan (rule 1) --------------------
    clock.tick()
    svc.register("FA", "3 Pine Rd")
    clock.tick()
    svc.out_for_delivery("FA")         # no "scanned" before -> violation
    clock.tick(5)
    svc.deliver("FA")

    # --- Fault B: re-routed AFTER delivery (rule 2) ----------------------
    clock.tick()
    svc.register("FB", "77 Birch Ln")
    clock.tick()
    svc.hub_scan("FB", "hub-c")
    clock.tick()
    svc.out_for_delivery("FB")
    clock.tick(3)
    svc.deliver("FB")                  # delivered (rule 3 satisfied)
    clock.tick(2)
    svc.route_to("FB", "hub-d")        # reroute after delivery -> violation

    # --- Fault C: not finished within the deadline (rule 3) --------------
    clock.tick()
    svc.register("FC", "5 Cedar Ct")
    clock.tick()
    svc.hub_scan("FC", "hub-e")
    clock.tick()
    svc.out_for_delivery("FC")
    clock.tick(DEADLINE + 1)           # 13s later: deadline already blown
    svc.deliver("FC")                  # a late delivery does not un-violate


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    # grace=0: the scripted trace is already in canonical order (fake clock,
    # no reordering), so the reorder window only delays deadline firing.
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES,
                    quiescence_ttl=QUIESCENCE_TTL, grace=0.0)
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
