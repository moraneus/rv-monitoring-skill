"""Runnable live demo of the library lending service under behave-rv.

    python demo.py

It starts the built-in web dashboard, then drives five loans in real time so
you can watch the three policies and the event log update live in the browser:

  * L1  healthy: borrow -> renew -> return, all in time (satisfies every rule)
  * L2  borrowed and then abandoned -> breaches the 21-second deadline (rule 3)
  * L3  reported lost and then renewed anyway -> breaks "never renew a lost
        loan" (rule 2)
  * L4  returned with no prior borrow -> breaks "return only after borrow"
        (rule 1)
  * L6  renewed with no prior borrow -> breaks "renew only after borrow"
        (rule 4)
  * M7  owes a fine, so renewing L7 is refused (nothing happens) until the
        fine is paid off -> "no renewal while fined" stays satisfied

The 21-second deadline for L2 fires on wall time while the stream is quiet, so
leave the demo running a few seconds past the last borrow to watch it flip to
violated. A service-relative clock (time.time() - start) keeps the dashboard
and the recorded trace readable and lets the wall-fired deadline resolve.

Set DEMO_AUTOEXIT=<seconds> to auto-shut-down for scripted runs; otherwise the
dashboard stays open until you press Ctrl-C.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.service import LendingService, LOAN_CLOSED             # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {LOAN_CLOSED}
PORT = 7007


def scripted_flows(svc: LendingService, until: float) -> None:
    """Drive the loans on a wall-time schedule (seconds from start)."""
    start = time.monotonic()

    def at(when: float, action) -> None:
        delay = when - (time.monotonic() - start)
        if delay > 0:
            time.sleep(delay)
        action()

    at(0.0, lambda: svc.borrow("L1", "M1", "C1"))
    at(1.0, lambda: svc.borrow("L2", "M2", "C2"))     # never acted on -> rule 3
    at(2.0, lambda: svc.borrow("L3", "M3", "C3"))
    at(3.0, lambda: svc.return_loan("L4"))            # no prior borrow -> rule 1
    at(5.0, lambda: svc.renew("L1"))
    at(7.0, lambda: svc.mark_lost("L3"))
    at(9.0, lambda: svc.renew("L3"))                  # renew after lost -> rule 2
    at(11.0, lambda: svc.return_loan("L1"))           # settles cleanly
    at(13.0, lambda: svc.renew("L6"))                 # no prior borrow -> rule 4

    # M7 owes a fine: the renew is refused (nothing happens) until they pay off.
    at(14.0, lambda: svc.borrow("L7", "M7", "C7"))
    at(15.0, lambda: svc.record_fine("M7"))           # M7 now owes
    at(16.0, lambda: svc.renew("L7"))                 # refused: no renewal while fined
    at(17.0, lambda: svc.pay_fine("M7"))              # M7 pays off
    at(18.0, lambda: svc.renew("L7"))                 # allowed now

    # Idle past L2's 21s deadline (armed at ~1s) so the timer fires live.
    while time.monotonic() - start < until:
        time.sleep(0.2)


def main() -> int:
    registry = build_registry()
    policies = load_policies(registry)

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "service.py")])

    start = time.time()
    clock = lambda: time.time() - start
    # TraceRecorder appends; start each session's trace fresh so replaying it
    # reflects exactly this run.
    live_trace = ROOT / "monitoring" / "traces" / "live_session.jsonl"
    live_trace.unlink(missing_ok=True)
    recorder = TraceRecorder(str(live_trace), clock=clock)
    svc = LendingService(
        lambda e: source.push(dashboard.tap(recorder(e))),
        clock=clock,
    )

    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    runner = threading.Thread(target=engine.run,
                              kwargs={"source": source, "sink": dashboard.sink},
                              daemon=True)
    runner.start()

    url = dashboard.start(port=PORT)
    print("live monitor:", url)
    print("Watch the three policy cards and the event feed. L2's 21-second")
    print("deadline fires ~22s in; leave it running to see it flip to violated.")

    autoexit = os.environ.get("DEMO_AUTOEXIT")
    horizon = float(autoexit) if autoexit else 26.0
    try:
        scripted_flows(svc, until=horizon)
        if autoexit:
            print(f"\nauto-exit after {horizon:.0f}s")
        else:
            print("\nScripted flows done. Dashboard still live - Ctrl-C to stop.")
            while True:
                time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        source.close()
        runner.join(timeout=5.0)
        recorder.close()
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
