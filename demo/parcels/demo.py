"""Runnable live demo of the parcel monitor.

    python demo.py                 # scripted real-time traffic, dashboard on :7202
    python demo.py --port 8080     # pick another port

Drives the REAL ParcelService in wall-clock time while a behave-rv engine
evaluates the three policies against the live event stream. Open the printed
URL to watch, in your own words:

  * each policy as a card with its per-parcel verdicts,
  * the rendered explanation for every violation (your scenario, replayed),
  * the live event feed,
  * the stability strip (code still matches the committed catalog).

Every event is also written to monitoring/traces/live_session.jsonl so the
exact run can be replayed later (see replay_trace.py).

Live mode uses a service-relative clock (seconds since start) and real time:
the 12-second deadline is 12 real seconds, so a parcel that is not finished in
time trips a wall-clock timer while you watch.
"""

from __future__ import annotations

import argparse
import atexit
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.parcel_service import ParcelService                    # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TRACE_PATH = "monitoring/traces/live_session.jsonl"


def run_traffic(svc: ParcelService) -> None:
    """A scripted stream of parcels in real time: three faults among the
    healthy majority, spaced so each verdict is visible as it lands."""

    def step(fn, *args, pause=0.6):
        fn(*args)
        time.sleep(pause)

    # Healthy: scanned, dispatched, delivered well within the deadline.
    step(svc.register, "P-1001", "12 Oak St")
    step(svc.hub_scan, "P-1001", "hub-north")
    step(svc.out_for_delivery, "P-1001")
    step(svc.deliver, "P-1001", pause=1.0)

    # Rule 1 fault: dispatched with NO hub scan -> violates at dispatch.
    step(svc.register, "P-1002", "9 Elm Ave")
    step(svc.out_for_delivery, "P-1002")
    step(svc.deliver, "P-1002", pause=1.0)

    # Rule 2 fault: re-routed AFTER delivery -> violates at the reroute.
    step(svc.register, "P-1004", "77 Birch Ln")
    step(svc.hub_scan, "P-1004", "hub-east")
    step(svc.out_for_delivery, "P-1004")
    step(svc.deliver, "P-1004")
    step(svc.route_to, "P-1004", "hub-west", pause=1.0)

    # Rule 3 fault: dispatched, then never finished -> the 12s wall timer
    # fires while the parcel sits quiet. Healthy P-1005 runs alongside so the
    # feed keeps moving.
    step(svc.register, "P-1003", "5 Cedar Ct")
    step(svc.hub_scan, "P-1003", "hub-south")
    step(svc.out_for_delivery, "P-1003", pause=1.5)

    step(svc.register, "P-1005", "40 Maple Way")
    step(svc.hub_scan, "P-1005", "hub-north")
    step(svc.out_for_delivery, "P-1005")
    step(svc.deliver, "P-1005", pause=1.0)

    # Wait out P-1003's deadline so the timeout verdict appears on the board.
    time.sleep(13)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7202)
    parser.add_argument("--seconds", type=float, default=0.0,
                        help="auto-stop this many seconds after traffic "
                             "finishes (0 = stay live until Ctrl-C)")
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start           # service-relative clock

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog="monitoring/catalog.json",
                          app=["app/parcel_service.py"])
    Path(TRACE_PATH).parent.mkdir(parents=True, exist_ok=True)
    recorder = TraceRecorder(TRACE_PATH, clock=clock)

    svc = ParcelService(
        emit=lambda event: source.push(dashboard.tap(recorder(event))),
        clock=clock,
    )

    # A small grace on a fast live stream; correctness does not depend on it
    # (behave-rv >= 0.3.1). No terminal event: delivered/returned parcels are
    # reclaimed by quiescence so rule 2 keeps watching after delivery.
    engine = Engine(policies, quiescence_ttl=120.0, grace=2.0)

    # Guarantee the trace's clock-horizon marker is written no matter how we
    # exit (Ctrl-C, kill, or clean auto-stop): without it a wall-fired
    # deadline verdict replays as pending instead of violated.
    atexit.register(recorder.close)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    url = dashboard.start(port=args.port)
    print("live monitor:", url, flush=True)
    print("watch the three policy cards fill in; three faults are seeded.",
          flush=True)

    engine_thread = threading.Thread(
        target=engine.run, args=(source,),
        kwargs={"sink": dashboard.sink}, daemon=True)
    engine_thread.start()

    try:
        run_traffic(svc)
        print("\nscripted traffic complete - dashboard still live at", url,
              flush=True)
        if args.seconds > 0:
            print(f"auto-stopping in {args.seconds:g}s.", flush=True)
            stop.wait(args.seconds)
        else:
            print("Ctrl-C to stop.", flush=True)
            stop.wait()
    finally:
        print("stopping...", flush=True)
        recorder.close()          # writes the clock-horizon marker for replay
        source.close()
        engine_thread.join(timeout=3)
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
