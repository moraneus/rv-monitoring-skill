"""Deterministic verdict gate: scripted traffic through the real FleetService
and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Every seeded flow (healthy and faulty) is driven with ``clock.tick`` between
ordered actions, so event times are distinct and ordering is exact. Update
EXPECTED only for intended behaviour changes, and say so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.service import FleetService                            # noqa: E402
from steps import build_registry, load_policies                # noqa: E402

TERMINAL_TYPES = {"device.retired"}     # a device's life ends at retirement
EXPECTED = {"verdicts": 43, "violations": 7}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically: one healthy device plus one
    device per rule that breaks that rule, one healthy sensor and one faulty."""
    clock = FakeClock()
    svc = FleetService(emit, clock=clock)

    def step(fn, *args):
        clock.tick()
        fn(*args)

    # dev-1: HEALTHY - satisfies all three device rules.
    step(svc.provision, "dev-1")
    step(svc.provision_passed, "dev-1")
    step(svc.activate, "dev-1")          # activated right after provision_ok
    step(svc.act, "dev-1", "ok")
    step(svc.act, "dev-1", "ok")
    step(svc.quarantine, "dev-1")
    step(svc.act, "dev-1", "blocked")    # only blocked actions after quarantine
    step(svc.wipe, "dev-1")              # wiped before retirement
    step(svc.retire, "dev-1")

    # dev-2: VIOLATES rule 1 - activated straight after a FAILED check.
    step(svc.provision, "dev-2")
    step(svc.provision_failed, "dev-2")
    step(svc.activate, "dev-2")          # predecessor is provision_fail, not _ok
    step(svc.act, "dev-2", "ok")
    step(svc.quarantine, "dev-2")
    step(svc.wipe, "dev-2")
    step(svc.retire, "dev-2")

    # dev-3: VIOLATES rule 2 - a successful action AFTER quarantine.
    step(svc.provision, "dev-3")
    step(svc.provision_passed, "dev-3")
    step(svc.activate, "dev-3")
    step(svc.act, "dev-3", "ok")
    step(svc.quarantine, "dev-3")
    step(svc.act, "dev-3", "ok")         # forbidden: ok action while quarantined
    step(svc.wipe, "dev-3")
    step(svc.retire, "dev-3")

    # dev-4: VIOLATES rule 3 - retired without ever being wiped.
    step(svc.provision, "dev-4")
    step(svc.provision_passed, "dev-4")
    step(svc.activate, "dev-4")
    step(svc.act, "dev-4", "ok")
    step(svc.retire, "dev-4")            # no wipe before retirement

    # sensor-1: HEALTHY - only ok readings (pends: a feed has no terminal).
    step(svc.sensor_reading, "sensor-1", "ok")
    step(svc.sensor_reading, "sensor-1", "ok")
    step(svc.sensor_reading, "sensor-1", "ok")

    # sensor-2: VIOLATES rule 4 - a non-ok reading.
    step(svc.sensor_reading, "sensor-2", "ok")
    step(svc.sensor_reading, "sensor-2", "ok")
    step(svc.sensor_reading, "sensor-2", "error")

    # quarantine surge: four devices quarantined AT ONCE trips the fleet alert
    # (rule 5). Each device stays otherwise healthy (rules 1-3 satisfied) so the
    # only new violation is the surge itself. Build the quarantine up before
    # draining it, so all four are held simultaneously.
    surge = ["dev-q1", "dev-q2", "dev-q3", "dev-q4"]
    for did in surge:
        step(svc.provision, did)
        step(svc.provision_passed, did)
        step(svc.activate, did)
        step(svc.quarantine, did)        # the 4th quarantine flags the surge
    for did in surge:
        step(svc.wipe, did)
        step(svc.retire, did)

    # dev-r1: HEALTHY under the stronger since rule (rule 6) - after quarantine
    # it does nothing but blocked rejections, then is decommissioned.
    step(svc.provision, "dev-r1")
    step(svc.provision_passed, "dev-r1")
    step(svc.activate, "dev-r1")
    step(svc.act, "dev-r1", "ok")
    step(svc.quarantine, "dev-r1")
    step(svc.act, "dev-r1", "blocked")
    step(svc.act, "dev-r1", "blocked")
    step(svc.wipe, "dev-r1")
    step(svc.retire, "dev-r1")

    # dev-r2: VIOLATES ONLY rule 6 - a FRESH PROVISIONING after quarantine.
    # Rule 2 (no ok action) and rule 1 (activation ordering) do not catch this;
    # the stronger since rule does - normal life resumed after quarantine.
    step(svc.provision, "dev-r2")
    step(svc.provision_passed, "dev-r2")
    step(svc.activate, "dev-r2")
    step(svc.act, "dev-r2", "ok")
    step(svc.quarantine, "dev-r2")
    step(svc.provision, "dev-r2")        # forbidden: back to normal life
    step(svc.wipe, "dev-r2")
    step(svc.retire, "dev-r2")


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
