"""Runnable demo: drive the LendingService live with behave-rv monitoring.

    python demo.py

It starts the built-in web dashboard, prints its URL, then drives a handful
of loans in real time so you can watch the three policies decide per loan and
watch the event log fill. The 21-second deadline (rule 3) is real wall-clock
time here, so one deliberately-abandoned loan trips it while you watch.

Open the printed URL. Each policy is a card with its per-loan verdicts; each
violation renders your own scenario with the failing step marked and the
deciding events; the live feed shows every emitted event; the strip at the
top shows whether the running code still matches the committed contract.

Press Ctrl+C to stop.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from behave_rv.engine.loop import Engine
from behave_rv.events.sources.replay import TraceRecorder
from behave_rv.events.sources.subscription import QueueSource
from behave_rv.dashboard import Dashboard

from app.lending_service import LendingService, TERMINAL_TYPE

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE / "monitoring"))
from steps import build_registry, load_policies  # noqa: E402

PORT = 7007
TRACE = HERE / "monitoring" / "traces" / "demo_session.jsonl"


def drive(svc: LendingService) -> None:
    """Real-time scripted traffic. Sleeps make each step watchable."""

    def wait(dt: float) -> None:
        time.sleep(dt)

    # L-1 healthy: borrowed, renewed, returned - all three policies stay green.
    svc.borrow("L-1", member_id="Alice", copy_id="C-Dune")
    wait(1)
    # L-2 will be ABANDONED: borrowed and never acted on -> trips the 21s
    # deadline (rule 3) while you watch.
    svc.borrow("L-2", member_id="Bob", copy_id="C-Neuromancer")
    wait(1)
    svc.renew("L-1")
    wait(1)
    # L-3 borrowed then reported lost.
    svc.borrow("L-3", member_id="Carol", copy_id="C-Solaris")
    wait(1)
    svc.report_lost("L-3")
    wait(1)
    svc.return_loan("L-1")               # L-1 completes cleanly
    wait(1)
    svc.renew("L-3")                     # rule 2 violation: renew after lost
    wait(1)
    svc.return_loan("L-4")               # rule 1 violation: return, never borrowed
    wait(1)
    svc.renew("L-6")                     # renew-after-borrow violation: never borrowed
    wait(1)
    # The fine guard, watchable in the event feed: Dana borrows, then owes a
    # fine, so her renewal is REFUSED (no renewed event appears); once she pays
    # it off the renewal goes through, and she returns the book in time.
    svc.borrow("L-5", member_id="Dana", copy_id="C-Foundation")
    wait(1)
    svc.record_fine("Dana", amount=2.50)
    wait(1)
    svc.renew("L-5")                     # refused: Dana owes -> nothing emitted
    wait(1)
    svc.pay_fine("Dana")
    wait(1)
    svc.renew("L-5")                     # now allowed
    wait(1)
    svc.return_loan("L-5")               # completes cleanly, well within 21s
    # Now go quiet. Around t=22s the abandoned L-2 trips the settle-within
    # deadline on the timer; a little later the never-settled renewals of L-3
    # and L-6 trip the renewal-window deadline too.


def main() -> int:
    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(HERE / "monitoring" / "catalog.json"),
                          app=[str(HERE / "app" / "lending_service.py")])
    recorder = TraceRecorder(str(TRACE))

    # Live wiring: every emitted event is recorded, shown on the dashboard,
    # and pushed to the engine. Service-relative clock so wall-clock deadlines
    # behave.
    svc = LendingService(lambda e: source.push(dashboard.tap(recorder(e))),
                         clock=lambda: time.time() - start)

    engine = Engine(policies, terminal_event_types={TERMINAL_TYPE}, grace=0.5)
    url = dashboard.start(port=PORT)
    print(f"live monitor: {url}")
    print("watch the three policy cards and the event feed; Ctrl+C to stop.")

    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    driver = threading.Thread(target=drive, args=(svc,), daemon=True)
    driver.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping.")
    finally:
        source.close()
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
