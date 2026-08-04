"""Deterministic verdict gate: scripted traffic through the real PaymentService
and the user's policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

Two sections, run through two independent engines so attribution is clean:

* HEALTHY -- every normal flow the user described (a disputed payment run to
  completion, and a clean captured->closed payment). These MUST produce zero
  violations. After the rules were narrowed to the user's intent (rule 1: no
  re-authorization/re-capture after a dispute; rule 2: only a *disputed* close
  needs a prior refund), both described flows are clean.

* FAULTS -- deliberately broken flows that SHOULD violate: a captured payment
  left to time out past 20s (rule 3), a frozen payment re-captured through a
  guard bypass (rule 1), and a disputed payment closed with no refund (rule 2).
  A fourth seed exercises rule 1's terminal window: a re-capture arriving AFTER
  the payment closed is NOT caught by the monitor (the frozen guard owns
  post-close protection), demonstrated rather than hidden.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from steps import build_registry, load_policies                 # noqa: E402
from app.service import PaymentService                           # noqa: E402

TERMINAL_TYPES = {"payment.closed"}

# The described healthy flows must be clean (no violations at all). The fault
# section must produce exactly this SET of settled verdicts - pinned as a set,
# not a count, so a compensating bug (a wrong violation replacing an expected
# one) cannot keep the gate green.
EXPECTED_FAULT = {
    ('every disputed payment that closes must have been refunded first', (('payment_id', 'pH'),), 'violated'),
    ('every disputed payment that closes must have been refunded first', (('payment_id', 'pW'),), 'satisfied'),
    ('once a payment is disputed no new charge activity may happen to it', (('payment_id', 'pG'),), 'violated'),
    ('once a payment is disputed no new charge activity may happen to it', (('payment_id', 'pH'),), 'satisfied'),
    ('once a payment is disputed no new charge activity may happen to it', (('payment_id', 'pW'),), 'satisfied'),
    ('once captured a payment must be closed or disputed within 20 seconds', (('payment_id', 'pF'),), 'violated'),
    ('once captured a payment must be closed or disputed within 20 seconds', (('payment_id', 'pG'),), 'satisfied'),
    ('once captured a payment must be closed or disputed within 20 seconds', (('payment_id', 'pH'),), 'satisfied'),
    ('once captured a payment must be closed or disputed within 20 seconds', (('payment_id', 'pW'),), 'satisfied'),
}


def settled_signature(v):
    """Order-independent identity for one settled verdict."""
    return (v.policy_id, tuple(sorted(v.entity_key.items())), v.verdict)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def _run(simulate) -> tuple[list, dict]:
    source = InProcessSource()
    simulate(source.emit)
    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    verdicts = engine.run(source, emit_pending=True)
    return verdicts, {p.policy_id: p for p in policies}


def simulate_healthy(emit) -> None:
    """Every normal flow the user described. Expected: zero violations."""
    clock = FakeClock()
    svc = PaymentService(emit, clock)

    # pA: a disputed payment, run through the full described resolution path.
    svc.authorize("pA");        clock.tick()
    svc.capture("pA");          clock.tick()
    svc.dispute("pA");          clock.tick()
    svc.investigate("pA");      clock.tick()
    svc.refund("pA");           clock.tick()
    svc.close("pA");            clock.tick()

    # pB: a never-disputed payment, closed directly after capture.
    svc.authorize("pB");        clock.tick()
    svc.capture("pB");          clock.tick()
    svc.close("pB");            clock.tick()


def simulate_faults(emit) -> None:
    """Deliberately broken flows that SHOULD violate."""
    clock = FakeClock()
    svc = PaymentService(emit, clock)

    # pF: captured then abandoned. An unrelated payment's activity 21s later
    # advances event time past the 20s deadline, firing rule 3 by absence.
    svc.authorize("pF");        clock.tick()
    svc.capture("pF");          clock.tick(21.0)
    svc.authorize("pZ")         # time-advancer; leaves only pending verdicts
    clock.tick()

    # pG: a frozen payment re-captured through a guard bypass -> rule 1. (The
    # real guard refuses this; calling capture() directly simulates the bug the
    # monitor exists to catch.)
    svc.authorize("pG");        clock.tick()
    svc.capture("pG");          clock.tick()
    svc.dispute("pG");          clock.tick()
    svc.capture("pG");          clock.tick()          # re-capture while frozen

    # pH: a disputed payment closed with no refund -> rule 2.
    svc.authorize("pH");        clock.tick()
    svc.capture("pH");          clock.tick()
    svc.dispute("pH");          clock.tick()
    svc.close("pH");            clock.tick()          # disputed close, no refund

    # pW: terminal window. Disputed, refunded, closed (clean under both rules),
    # then a re-capture AFTER the terminal. Rule 1's instance settled at the
    # terminal, so the post-close re-capture spawns a fresh, scope-closed
    # instance and is NOT caught -- the frozen guard owns post-close protection.
    svc.authorize("pW");        clock.tick()
    svc.capture("pW");          clock.tick()
    svc.dispute("pW");          clock.tick()
    svc.refund("pW");           clock.tick()
    svc.close("pW");            clock.tick()          # emits terminal payment.closed
    svc.capture("pW")           # post-terminal re-capture, invisible to rule 1


def _report(label: str, verdicts: list, by_id: dict) -> int:
    violations = [v for v in verdicts if v.verdict == "violated"]
    print(f"\n=== {label} ===")
    for v in verdicts:
        print(f"{v.verdict:9}  {v.entity_key}  {v.policy_id}")
    for v in violations:
        policy = by_id[v.policy_id]
        print()
        print(explain_verdict(v, policy.authored_scenario, policy.failing_step_index))
    print(f"\n{label}: {len(verdicts)} verdicts, {len(violations)} violation(s)")
    return len(violations)


def main() -> int:
    healthy_v, healthy_by = _run(simulate_healthy)
    fault_v, fault_by = _run(simulate_faults)

    healthy_violations = _report("HEALTHY (described flows, must be clean)",
                                 healthy_v, healthy_by)
    _report("FAULTS (must violate)", fault_v, fault_by)

    ok = True
    if healthy_violations != 0:
        ok = False
        print(f"\nCONFLICT: {healthy_violations} violation(s) on the described "
              "HEALTHY flows (expected none). Rules 1 and 2 as written forbid "
              "lifecycles the user described. This gate stays RED until the user "
              "resolves it (see SUGGESTED_POLICIES.md).")

    fault_settled = {settled_signature(v) for v in fault_v
                     if v.verdict in ("violated", "satisfied")}
    if not EXPECTED_FAULT:
        print("\nEXPECTED_FAULT not pinned yet. Set it to this exact set:")
        for s in sorted(fault_settled):
            print(f"    {s!r},")
        return 1
    missing = EXPECTED_FAULT - fault_settled
    unexpected = fault_settled - EXPECTED_FAULT
    for s in sorted(missing):
        print("MISSING (expected, did not occur):", s)
    for s in sorted(unexpected):
        print("UNEXPECTED (occurred, not pinned):", s)
    if missing or unexpected:
        ok = False

    print("\n" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
