"""Deterministic verdict gate: scripted traffic through the real FleetService
and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Every seeded flow (healthy and faulty) is driven with a fake clock and
``clock.tick`` between ordered actions. EXPECTED is pinned; update it only for
intended behaviour changes, and say so in the commit/report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource   # noqa: E402
from behave_rv.verdict.explain import explain_verdict            # noqa: E402

from app.service import FleetService                             # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {"device.retired"}     # keep in sync with the application

# Pinned after review of the output below. Conclusive violations:
#   dev-badact      -> policy 1 (activation not right after provision_ok)
#   dev-quar-bad    -> policy 2 (a normal action after quarantine: not contained)
#   dev-wipe-bad    -> policy 3 (retired without a prior wipe)
#   sensor-bad      -> policy 4 (a non-ok reading)
#   fleet           -> policy 5 (>3 devices quarantined at once: surge alert)
# dev-decom (quarantine -> blocked -> wipe -> retire) is now all green under
# Option A: rule 2 holds (wipe is "contained"), rule 3 satisfied - it adds no
# violation. Healthy invariants with no terminal (dev-quar-ok, sensor-ok, the
# attack-* devices' policy-2 instances) report pending, not satisfied.
EXPECTED = {"violations": 5}


class FakeClock:
    def __init__(self):
        self.now = 1_000.0     # any magnitude works; distinct per ordered action

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically, healthy and faulty."""
    clock = FakeClock()
    svc = FleetService(emit, clock=clock)

    def step(fn, *args):
        fn(*args)
        clock.tick()          # distinct timestamps for ordered actions

    # -- attack wave: >3 devices quarantined at once (rule 5 surge) -------
    # Run first, while the fleet is clear, so the 4th quarantine is the crossing.
    for d in ("attack-1", "attack-2", "attack-3", "attack-4"):
        step(svc.provision, d)
        step(svc.provision_ok, d)
        step(svc.quarantine, d)             # attack-4 -> one fleet surge event

    # -- dev-clean: full healthy lifecycle -------------------------------
    # activation right after provision_ok (rule 1 ok); wiped before retire
    # (rule 3 ok).
    step(svc.provision, "dev-clean")
    step(svc.provision_ok, "dev-clean")
    step(svc.activate, "dev-clean")
    step(svc.act, "dev-clean", "report-telemetry")
    step(svc.wipe, "dev-clean")
    step(svc.retire, "dev-clean")

    # -- dev-badact: activated without provision_ok immediately before ----
    # predecessor of "activated" is "provisioned" -> rule 1 violated.
    step(svc.provision, "dev-badact")
    step(svc.activate, "dev-badact")

    # -- dev-quar-ok: quarantine then only blocked actions (rule 2 holds) --
    step(svc.provision, "dev-quar-ok")
    step(svc.provision_ok, "dev-quar-ok")
    step(svc.activate, "dev-quar-ok")
    step(svc.quarantine, "dev-quar-ok")
    step(svc.blocked, "dev-quar-ok", "remote-exec")
    step(svc.blocked, "dev-quar-ok", "config-push")

    # -- dev-quar-bad: a normal action AFTER quarantine (rule 2 violated) --
    step(svc.provision, "dev-quar-bad")
    step(svc.provision_ok, "dev-quar-bad")
    step(svc.activate, "dev-quar-bad")
    step(svc.quarantine, "dev-quar-bad")
    step(svc.act, "dev-quar-bad", "report-telemetry")   # not blocked -> violation

    # -- dev-wipe-bad: retired without ever being wiped (rule 3 violated) --
    step(svc.provision, "dev-wipe-bad")
    step(svc.provision_ok, "dev-wipe-bad")
    step(svc.activate, "dev-wipe-bad")
    step(svc.retire, "dev-wipe-bad")

    # -- dev-decom: clean decommission path, all green under Option A --------
    # quarantine -> blocked -> wipe -> retire: every post-quarantine event is
    # "contained" (rule 2 holds), wiped precedes retire (rule 3 ok).
    step(svc.provision, "dev-decom")
    step(svc.provision_ok, "dev-decom")
    step(svc.activate, "dev-decom")
    step(svc.quarantine, "dev-decom")
    step(svc.blocked, "dev-decom", "remote-exec")
    step(svc.wipe, "dev-decom")
    step(svc.retire, "dev-decom")

    # -- sensor-ok: only ok readings (rule 4 holds) ----------------------
    step(svc.sensor_reading, "sensor-ok", "ok", 21.4)
    step(svc.sensor_reading, "sensor-ok", "ok", 21.6)
    step(svc.sensor_reading, "sensor-ok", "ok", 21.5)

    # -- sensor-bad: a non-ok reading (rule 4 violated) ------------------
    step(svc.sensor_reading, "sensor-bad", "ok", 19.9)
    step(svc.sensor_reading, "sensor-bad", "ok", 20.1)
    step(svc.sensor_reading, "sensor-bad", "error", -1.0)   # -> violation


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
    ok = len(violations) == EXPECTED["violations"]
    if not ok:
        print(f"UNEXPECTED: pinned {EXPECTED['violations']} violation(s), "
              f"got {len(violations)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
