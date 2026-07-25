"""Runnable live demo of the library lending service under behave-rv.

    python demo.py                 # opens the live dashboard, drives traffic

It starts the built-in web dashboard, wires the real ``LendingService`` to the
running monitor, and then drives a scripted stream of loans in real time so you
can watch the five policies decide, live:

  * healthy loans (borrow -> return, borrow -> renew -> return, borrow -> lost)
    stay green;
  * a return with no prior borrow turns "returned only after borrowed" red;
  * a renewal with no prior borrow turns "renewed only after borrowed" red;
  * a renewal after a copy was reported lost turns "lost never renewed" red;
  * a renewal after the copy was returned turns "returned never renewed" red;
  * a loan left open turns "settled within 21 seconds" red when its deadline
    passes - fired by the monitor's own timer, with no event arriving.

Open the printed URL. Each policy is a card showing its per-loan verdicts; a
violation renders as the authored scenario with the failing step marked and the
deciding events listed. The raw event feed and the stability strip (code vs the
committed contract) are on the same page. Press Ctrl-C to stop.
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
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.service import LendingService                          # noqa: E402
from steps import build_registry, load_policies                # noqa: E402

PORT = 7201
QUIESCENCE_TTL = 3600.0     # no terminal event (see steps.py / the report);
                            # loans are reclaimed by this quiescence timeout.


def drive(svc: LendingService, stop: threading.Event) -> None:
    """A scripted real-time stream of loans. Delays are seconds of wall time so
    the deadline (rule 3) is watchable."""
    def wait(dt):
        stop.wait(dt)

    # Healthy: borrowed and returned quickly.
    svc.borrow("L-101", "alice", "copy-hobbit"); wait(1)
    # Healthy: borrowed, will be renewed then returned.
    svc.borrow("L-102", "bob", "copy-dune"); wait(1)
    # Overdue: borrowed and never settled -> rule 3 fires at ~t+21s.
    svc.borrow("L-777", "carol", "copy-1984"); wait(1)

    svc.return_("L-101"); wait(2)                # L-101 done, green
    svc.return_("L-303"); wait(2)                # no prior borrow -> rule 1 red
    svc.renew("L-606"); wait(2)                  # no prior borrow -> policy 4 red

    svc.renew("L-102"); wait(2)                  # legitimate renewal
    svc.borrow("L-404", "dave", "copy-sapiens"); wait(2)
    svc.report_lost("L-404"); wait(2)            # copy lost, loan closed

    svc.return_("L-102"); wait(2)                # L-102 done, green
    svc.renew("L-404"); wait(1)                  # renew after lost -> rule 2 red

    # A loan returned normally, then a stray renewal after the close -> policy 5.
    svc.borrow("L-505", "erin", "copy-emma"); wait(1)
    svc.return_("L-505"); wait(2)
    svc.renew("L-505"); wait(1)                  # renew after return -> policy 5 red

    # From here nothing arrives for L-777; its 21s deadline elapses on the
    # monitor's wall-clock timer and rule 3 turns red on the page.


def main() -> int:
    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start          # service-relative time: keeps
                                                  # dashboards/traces readable and
                                                  # wall-fired deadlines correct.
    source = QueueSource()
    recorder = TraceRecorder(str(ROOT / "monitoring" / "traces" / "live_session.jsonl"),
                             clock=clock)
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "service.py")])
    svc = LendingService(lambda e: source.push(dashboard.tap(recorder(e))),
                         clock=clock)

    url = dashboard.start(port=PORT)
    print("live monitor:", url)
    print("watch the three policy cards decide; press Ctrl-C to stop.")

    engine = Engine(policies, quiescence_ttl=QUIESCENCE_TTL, grace=0.5)
    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    stop = threading.Event()
    driver = threading.Thread(target=drive, args=(svc, stop), daemon=True)
    driver.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        stop.set()
        source.close()
        recorder.close()      # writes a clock-horizon marker so the wall-fired
                              # deadline verdict replays instead of pending
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
