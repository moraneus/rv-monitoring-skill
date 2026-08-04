"""Deterministic verdict gate: scripted fleet traffic through the real service
and policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The scripted traffic includes EVERY healthy flow the user described (they must
produce ZERO violations -- a violation on a described healthy flow would mean
the six rules jointly forbid a lifecycle the user relies on), plus one seeded
fault per rule so each rule is proven to fire.

Terminal-window seed: rule 02 is a SCOPED prohibition on an entity (the device)
that has a terminal event (device.retired). A terminal settles a prohibition as
satisfied, so the rule is only armed from quarantine until retirement. The
D-WINDOW device below fires a non-blocked action AFTER retirement to make that
boundary visible: it is NOT caught by rule 02 (a fresh, unquarantined
instance), which is the honest guarantee window for rule 02, not a bug.

NOTE the coupling with rule 05: that same post-retirement "ok" action lands on
a FRESH instance with no activation history, so rule 05 ("actions only after
activation") DOES flag it. A post-retirement non-blocked action is therefore
invisible to rule 02 but visible to rule 05 -- which is why the pinned
violation count is 7 (one per rule = 6, plus this D-WINDOW rule-05 hit). This
interaction is surfaced to the user; the pins encode the current, sanctioned
behaviour.

Update EXPECTED only for intended behaviour changes, and say so in the commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                              # noqa: E402
from behave_rv.events.sources.replay import ReplaySource, record_events  # noqa: E402
from behave_rv.verdict.explain import explain_verdict                 # noqa: E402

from app.fleet import RETIRED_TYPE, FleetService                      # noqa: E402
from steps import build_registry, load_policies                      # noqa: E402

TERMINAL_TYPES = {RETIRED_TYPE}
TRACE = Path(__file__).resolve().parent / "traces" / "replay_check.jsonl"

# Pinned as an intended change (six adopted rules, expanded traffic).
# verdicts = total emitted (incl. pendings); violations = one seeded fault per
# rule (6) plus the D-WINDOW post-retirement action that rule 05 flags (see the
# module docstring's terminal-window note) = 7.
EXPECTED = {
    ('a device is only quarantined after it was activated', (('device_id', 'D-1'),), 'satisfied'),
    ('a device is only quarantined after it was activated', (('device_id', 'D-BAD2'),), 'satisfied'),
    ('a device is only quarantined after it was activated', (('device_id', 'D-BAD6'),), 'violated'),
    ('a device is only quarantined after it was activated', (('device_id', 'D-WINDOW'),), 'satisfied'),
    ('a device may only be activated immediately after its provision check passed', (('device_id', 'D-1'),), 'satisfied'),
    ('a device may only be activated immediately after its provision check passed', (('device_id', 'D-BAD1'),), 'violated'),
    ('a device may only be activated immediately after its provision check passed', (('device_id', 'D-BAD2'),), 'satisfied'),
    ('a device may only be activated immediately after its provision check passed', (('device_id', 'D-BAD3'),), 'satisfied'),
    ('a device may only be activated immediately after its provision check passed', (('device_id', 'D-WINDOW'),), 'satisfied'),
    ('a device performs actions only after it was activated', (('device_id', 'D-1'),), 'satisfied'),
    ('a device performs actions only after it was activated', (('device_id', 'D-BAD2'),), 'satisfied'),
    ('a device performs actions only after it was activated', (('device_id', 'D-BAD5'),), 'violated'),
    ('a device performs actions only after it was activated', (('device_id', 'D-WINDOW'),), 'violated'),
    ('a quarantined device performs no non-blocked action', (('device_id', 'D-1'),), 'satisfied'),
    ('a quarantined device performs no non-blocked action', (('device_id', 'D-BAD2'),), 'violated'),
    ('a quarantined device performs no non-blocked action', (('device_id', 'D-BAD3'),), 'satisfied'),
    ('a quarantined device performs no non-blocked action', (('device_id', 'D-WINDOW'),), 'satisfied'),
    ('a sensor feed only ever reports ok readings', (('sensor_id', 'S-BAD'),), 'violated'),
    ('every retired device was wiped before retirement', (('device_id', 'D-1'),), 'satisfied'),
    ('every retired device was wiped before retirement', (('device_id', 'D-BAD3'),), 'violated'),
    ('every retired device was wiped before retirement', (('device_id', 'D-WINDOW'),), 'satisfied'),
}


def settled_signature(v):
    """Order-independent identity for one settled verdict."""
    return (v.policy_id, tuple(sorted(v.entity_key.items())), v.verdict)


class FakeClock:
    """Deterministic time: tick() advances it. Same traffic -> same trace."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(events: list) -> None:
    """Drive every seeded flow deterministically. tick() between ordered
    actions so events whose order matters carry distinct timestamps."""
    clock = FakeClock()
    svc = FleetService(events.append, clock=clock)

    # -- HEALTHY device: the full lifecycle the user described.
    #    provisioned -> provision_ok -> activated -> acts -> quarantined ->
    #    (only blocked actions) -> wiped -> retired.  Satisfies rules 01/02/03.
    svc.provision("D-1");                       clock.tick()
    svc.record_provision_check("D-1", True);    clock.tick()   # provision_ok
    svc.activate("D-1");                        clock.tick()   # rule 01: ok
    svc.perform_action("D-1", "ok");            clock.tick()
    svc.perform_action("D-1", "ok");            clock.tick()
    svc.quarantine("D-1");                      clock.tick()
    svc.perform_action("D-1", "blocked");       clock.tick()   # rule 02: honored
    svc.wipe("D-1");                            clock.tick()   # rule 03: wiped...
    svc.retire("D-1");                          clock.tick()   # ...before retire

    # -- HEALTHY sensor feed: only ok readings.  Satisfies rule 04 (stays
    #    pending -- an unbounded feed has no terminal, so it is never
    #    "satisfied", but it is never violated either).
    svc.sensor_reading("S-1", "ok");            clock.tick()
    svc.sensor_reading("S-1", "ok");            clock.tick()
    svc.sensor_reading("S-1", "ok");            clock.tick()

    # -- FAULT, rule 01: activated without the provision check passing.
    #    The event immediately before "activated" is "provision_failed",
    #    not "provision_ok" -> violated.
    svc.provision("D-BAD1");                        clock.tick()
    svc.record_provision_check("D-BAD1", False);    clock.tick()  # provision_failed
    svc.activate("D-BAD1");                         clock.tick()  # rule 01: VIOLATION

    # -- FAULT, rule 02: a compromised device reports a normal action AFTER
    #    quarantine instead of a blocked rejection -> violated.
    svc.provision("D-BAD2");                        clock.tick()
    svc.record_provision_check("D-BAD2", True);     clock.tick()
    svc.activate("D-BAD2");                         clock.tick()
    svc.quarantine("D-BAD2");                       clock.tick()
    svc.perform_action("D-BAD2", "ok");            clock.tick()  # rule 02: VIOLATION

    # -- FAULT, rule 03: retired without ever being wiped -> violated.
    svc.provision("D-BAD3");                        clock.tick()
    svc.record_provision_check("D-BAD3", True);     clock.tick()
    svc.activate("D-BAD3");                         clock.tick()
    svc.retire("D-BAD3");                           clock.tick()  # rule 03: VIOLATION

    # -- FAULT, rule 04: a sensor feed reports a non-ok reading -> violated.
    svc.sensor_reading("S-BAD", "ok");             clock.tick()
    svc.sensor_reading("S-BAD", "fault");          clock.tick()  # rule 04: VIOLATION

    # -- FAULT, rule 05: a device reports an action but was never activated
    #    (D-1 already exercises the healthy case: activated before its actions).
    svc.provision("D-BAD5");                        clock.tick()
    svc.record_provision_check("D-BAD5", True);     clock.tick()
    svc.perform_action("D-BAD5", "ok");            clock.tick()  # rule 05: VIOLATION

    # -- FAULT, rule 06: a device is quarantined but was never activated
    #    (D-1 already exercises the healthy case: activated before quarantine).
    svc.provision("D-BAD6");                        clock.tick()
    svc.record_provision_check("D-BAD6", True);     clock.tick()
    svc.quarantine("D-BAD6");                       clock.tick()  # rule 06: VIOLATION

    # -- TERMINAL-WINDOW seed: a non-blocked action arriving AFTER retirement.
    #    The device.retired terminal already settled rule 02 as satisfied, so
    #    this stray action lands on a FRESH instance. RULE 02 does NOT catch it
    #    (its honest guarantee window is quarantine..retirement). RULE 05 DOES
    #    catch it: the fresh instance has no activation history, so an "ok"
    #    action without a prior activation violates "actions only after
    #    activation". Hence one violation from this seed, attributed to rule 05.
    svc.provision("D-WINDOW");                      clock.tick()
    svc.record_provision_check("D-WINDOW", True);   clock.tick()
    svc.activate("D-WINDOW");                       clock.tick()
    svc.quarantine("D-WINDOW");                     clock.tick()
    svc.perform_action("D-WINDOW", "blocked");     clock.tick()
    svc.wipe("D-WINDOW");                           clock.tick()
    svc.retire("D-WINDOW");                         clock.tick()  # terminal settles rule 02
    svc.perform_action("D-WINDOW", "ok");          clock.tick()  # post-terminal: rule 02 misses, rule 05 flags


def main() -> int:
    events: list = []
    simulate_traffic(events)
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    record_events(TRACE, events)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    verdicts = engine.run(ReplaySource(TRACE), emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for v in verdicts:
        entity = ", ".join(f"{k}={val}" for k, val in v.entity_key.items())
        print(f"{v.verdict:9}  {entity:18}  {v.policy_id}")
    for v in violations:
        policy = by_id[v.policy_id]
        print()
        print(explain_verdict(v, policy.authored_scenario,
                              policy.failing_step_index))

    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s)")
    settled = {settled_signature(v) for v in verdicts
               if v.verdict in ("violated", "satisfied")}
    print()
    print(f"{len(verdicts)} verdicts, {len(violations)} violation(s), "
          f"{len(settled)} settled")
    if not EXPECTED:
        print("EXPECTED not pinned yet. Review the verdicts above, then set "
              "EXPECTED to this exact set:")
        for s in sorted(settled):
            print(f"    {s!r},")
        return 1
    missing = EXPECTED - settled
    unexpected = settled - EXPECTED
    for s in sorted(missing):
        print("MISSING (expected, did not occur):", s)
    for s in sorted(unexpected):
        print("UNEXPECTED (occurred, not pinned):", s)
    ok = not missing and not unexpected
    print("GATE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
