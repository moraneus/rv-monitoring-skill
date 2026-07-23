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

from behave_rv.engine.loop import Engine                       # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.service import LendingService                          # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {"loan.closed"}     # keep in sync with the application
EXPECTED = {"verdicts": 36, "violations": 5}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def simulate_traffic(emit) -> None:
    """Drive every seeded flow deterministically.

    Five loans exercise every rule: one healthy, one that breaches the
    21-second deadline, one renewed after being reported lost, one returned
    with no prior borrow, and a late healthy loan that advances event time
    past the deadline so the timer resolves.
    """
    clock = FakeClock()
    svc = LendingService(emit, clock=clock)

    # L1: healthy - borrow, renew, return, all in time.
    svc.borrow("L1", "M1", "C1")
    clock.tick()                       # t=1
    svc.borrow("L2", "M2", "C2")       # L2: borrowed, then never acted on
    clock.tick()                       # t=2
    svc.borrow("L3", "M3", "C3")
    clock.tick()                       # t=3
    svc.return_loan("L4")              # L4: returned with no prior borrow (rule 1)
    clock.tick()                       # t=4
    svc.renew("L1")
    clock.tick()                       # t=5
    svc.mark_lost("L3")
    clock.tick(3)                      # t=8
    svc.renew("L3")                    # L3: renewed after lost (rule 2)
    clock.tick(2)                      # t=10
    svc.return_loan("L1")              # L1 settles cleanly (renewed within 21s)
    clock.tick(3)                      # t=13
    svc.renew("L6")                    # L6: renewed with no prior borrow (rule 4)

    # M7/L7: the fine feature. While M7 owes, the renew is refused (no event),
    # so the "no renewal while fined" policy stays satisfied; after paying off,
    # the renewal is allowed.
    clock.tick()                       # t=14
    svc.borrow("L7", "M7", "C7")
    clock.tick()                       # t=15
    svc.record_fine("M7")              # M7 now owes a fine
    clock.tick()                       # t=16
    svc.renew("L7")                    # refused: M7 owes -> no renewal happens
    clock.tick()                       # t=17
    svc.pay_fine("M7")                 # M7 pays off
    clock.tick()                       # t=18
    svc.renew("L7")                    # allowed now: renewal extends the loan

    # L5: late healthy loan - advances event time past L2's 21s deadline
    # so the timer resolves it to violated on replay.
    clock.tick(10)                     # t=28
    svc.borrow("L5", "M5", "C5")
    clock.tick()                       # t=29
    svc.renew("L5")
    clock.tick()                       # t=30
    svc.return_loan("L5")


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
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
