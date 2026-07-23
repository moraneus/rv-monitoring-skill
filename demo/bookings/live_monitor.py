"""Run the studio's booking service LIVE with the monitor and the web
dashboard attached.

    python live_monitor.py                 # serves ~35s of seeded traffic
    python live_monitor.py --seconds 60

Open the printed URL (default http://127.0.0.1:7007). You will see each of
your policies as a card with its per-booking verdicts, the explanation for
every violation rendered as your own scenario with the real booking's events,
the live event feed, and a strip showing whether the code still matches the
committed contract.

Wiring (nothing blocks the app):

  app thread --push--> QueueSource --> Engine (own thread)
                                          |
        browser <-- Dashboard (http) <-- sink
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from app.booking_service import TERMINAL_TYPE, BookingService       # noqa: E402
from steps import build_registry, load_policies                    # noqa: E402

from behave_rv.dashboard import Dashboard                          # noqa: E402
from behave_rv.engine.loop import Engine                           # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder          # noqa: E402
from behave_rv.events.sources.subscription import QueueSource      # noqa: E402

PROMOTION_DEADLINE = 15.0   # matches policy 04; the timeout booking waits past it


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=35.0,
                        help="how long to keep serving before shutting down")
    parser.add_argument("--port", type=int, default=7007)
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    # service-relative event times keep the dashboard timeline readable (raw
    # time.time() also works since 0.3.0; this is a readability choice).
    start = time.time()
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=ROOT / "monitoring" / "catalog.json",
                          app=[ROOT / "app" / "booking_service.py"])
    recorder = TraceRecorder(ROOT / "monitoring" / "traces" / "live_session.jsonl")
    svc = BookingService(lambda e: source.push(dashboard.tap(recorder(e))),
                         clock=lambda: time.time() - start)

    url = dashboard.start(port=args.port)
    print("live monitor:", url)
    engine = Engine(policies, terminal_event_types={TERMINAL_TYPE}, grace=0.5)
    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=dashboard.sink), daemon=True)
    engine_thread.start()

    def traffic():
        # A healthy booking: reserve -> confirm -> check in -> attended.
        svc.reserve("B-1001", "M-1", "C-1"); time.sleep(0.4)
        svc.confirm("B-1001", "M-1", "C-1"); time.sleep(0.4)

        # A waitlisted booking promoted and confirmed IN TIME (satisfies 04).
        svc.reserve("B-1002", "M-2", "C-1"); time.sleep(0.3)
        svc.waitlist("B-1002"); time.sleep(0.3)
        svc.promote("B-1002"); time.sleep(0.3)

        # The nightmare: a booking cancelled, then someone checks in anyway.
        svc.reserve("B-1004", "M-4", "C-3"); time.sleep(0.3)
        svc.confirm("B-1004", "M-4", "C-3"); time.sleep(0.3)

        # A member who owes a balance, then a booking gets confirmed for them.
        svc.incur_balance("M-7"); time.sleep(0.3)
        svc.reserve("B-1007", "M-7", "C-5"); time.sleep(0.3)

        # The booking whose promotion will TIME OUT: promote and then leave it.
        # The engine's timer fires the violation ~15s later, with nothing else
        # needing to happen - the absence is the violation.
        svc.reserve("B-1003", "M-3", "C-2"); time.sleep(0.3)
        svc.waitlist("B-1003"); time.sleep(0.3)
        svc.promote("B-1003"); time.sleep(0.6)

        # Finish the healthy flows.
        svc.check_in("B-1001"); time.sleep(0.4)
        svc.mark_attended("B-1001"); time.sleep(0.4)
        svc.confirm("B-1002", "M-2", "C-1"); time.sleep(0.3)
        svc.check_in("B-1002"); time.sleep(0.3)
        svc.mark_attended("B-1002"); time.sleep(0.3)

        # The forbidden confirmation while the balance is still owed (violates 03).
        svc.confirm("B-1007", "M-7", "C-5"); time.sleep(0.4)

        # Spring the nightmare: check in the already-cancelled booking (violates 01).
        svc.cancel("B-1004"); time.sleep(0.6)
        svc.check_in("B-1004")
        # ...and now everyone waits for B-1003's 15s promotion timer to fire.

    threading.Thread(target=traffic, daemon=True).start()

    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    source.close()
    engine_thread.join(timeout=5)
    dashboard.stop()
    recorder.close()
    counts = dashboard.state()["counts"]
    print(f"done: {engine.verdicts_delivered} verdicts delivered "
          f"({counts['violations']} violations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
