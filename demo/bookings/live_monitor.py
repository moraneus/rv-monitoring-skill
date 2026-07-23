"""Run the booking monitor live, with the built-in dashboard.

    python live_monitor.py        # then open the printed URL

Your app threads push booking events into a thread-safe QueueSource; the
engine consumes them on its own thread; every verdict lands on the dashboard.
The dashboard shows each policy as a card with its per-booking verdicts, the
authored scenario replayed with real values for any violation, the live event
feed, and the two-sided stability strip (does the running code still match the
committed contract). Nothing here blocks the studio's booking logic.

Timestamps use a SERVICE-RELATIVE clock (time.time() - start) so the 15-second
promotion deadline fires correctly on wall time when a booking goes quiet.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402

from app.booking_service import BookingService, TERMINAL_TYPE   # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

PORT = 7007
C = "spin-0700"            # the class session everyone in this demo books into


def drive(svc, pace=0.6):
    """Seed a representative afternoon, paced so the page updates visibly."""
    def beat(fn, *args):
        fn(*args)
        time.sleep(pace)

    # Healthy: reserve -> confirm -> check in -> attend (all green).
    beat(svc.reserve, "B-100", "M-alice", C)
    beat(svc.confirm, "B-100", "M-alice", C)
    beat(svc.check_in, "B-100", "M-alice", C)
    beat(svc.mark_attended, "B-100", "M-alice", C)

    # P4: confirmed while the member still owes money.
    beat(svc.reserve, "B-OWING", "M-dan", C)
    beat(svc.confirm, "B-OWING", "M-dan", C, "owing", "none")

    # P5: confirmed despite the app's duplicate flag.
    beat(svc.reserve, "B-FLAGGED", "M-erin", C)
    beat(svc.confirm, "B-FLAGGED", "M-erin", C, "clear", "duplicate")

    # P3: checked in without ever being confirmed.
    beat(svc.reserve, "B-NOCONFIRM", "M-gina", C)
    beat(svc.check_in, "B-NOCONFIRM", "M-gina", C)

    # P7: marked attended with no check-in.
    beat(svc.reserve, "B-ATTEND-NOCHECK", "M-hank", C)
    beat(svc.confirm, "B-ATTEND-NOCHECK", "M-hank", C)
    beat(svc.mark_attended, "B-ATTEND-NOCHECK", "M-hank", C)

    # P6 amber: a booking that just sits, never reaching an end state.
    beat(svc.reserve, "B-STUCK", "M-ivy", C)

    # P2: promoted, then left to time out - the 15s wall-clock timer fires it.
    beat(svc.waitlist, "B-PROMO-LATE", "M-carol", C)
    beat(svc.promote, "B-PROMO-LATE", "M-carol", C)

    # P1 (the 3am nightmare): cancel, then still show up and check in.
    beat(svc.reserve, "B-CANCEL-RETURN", "M-fred", C)
    beat(svc.confirm, "B-CANCEL-RETURN", "M-fred", C)
    beat(svc.cancel, "B-CANCEL-RETURN", "M-fred", C)
    time.sleep(2.0)
    beat(svc.check_in, "B-CANCEL-RETURN", "M-fred", C)


def main() -> int:
    registry = build_registry()
    policies = load_policies(registry)

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "booking_service.py")])
    recorder = TraceRecorder(ROOT / "monitoring" / "traces" / "live_session.jsonl")

    start = time.time()
    svc = BookingService(lambda e: source.push(dashboard.tap(recorder(e))),
                         clock=lambda: time.time() - start)

    engine = Engine(policies, terminal_event_types={TERMINAL_TYPE},
                    quiescence_ttl=3600.0, grace=0.5)
    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    url = dashboard.start(port=PORT)
    print("live monitor:", url)
    print("driving seeded booking traffic; watch the policy cards update...")

    drive(svc)

    # Keep the process (and the page) alive long enough for the 15s promotion
    # deadline to fire and for you to explore. Ctrl-C to stop.
    print("seeding done. the promotion deadline will fire ~15s after promote; "
          "leaving the monitor up. Ctrl-C to quit.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nstopping.")
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
