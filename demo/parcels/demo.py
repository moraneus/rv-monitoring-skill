"""Live monitoring demo for the parcel service.

    python demo.py                 # runs, opens the dashboard, waits for Ctrl-C
    python demo.py --seconds 24    # runs for a fixed span, then shuts down

Wiring, in words: seeded parcel traffic runs on a driver thread and pushes
events into a QueueSource through the dashboard tap and a trace recorder; the
engine consumes on its own thread and delivers each verdict to the dashboard
sink; the stdlib HTTP dashboard serves live snapshots. Nothing blocks the app.

Open the printed URL to watch, in your own words: every policy as a card with
its per-parcel verdicts, the authored scenario replayed with the failing step
marked for each violation, the live event feed, and the stability strip
showing whether the code still matches the committed catalog.

The clock is service-relative (``time.time() - start``) so wall-fired deadline
timers (the 12s delivery window) start near zero and fire correctly.
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

from behave_rv.dashboard import Dashboard                        # noqa: E402
from behave_rv.engine.loop import Engine                         # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource    # noqa: E402

from app.parcel_service import ParcelService                     # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402

TRACE_PATH = ROOT / "monitoring" / "traces" / "live_session.jsonl"


def drive(svc: ParcelService, stop: threading.Event) -> None:
    """Seeded parcel traffic: three healthy parcels and three faults, paced so
    the policy cards flip live on the dashboard."""

    def gap(dt=0.9):
        stop.wait(dt)

    # P-1 healthy: scanned, out for delivery, delivered in time.
    svc.register("P-1", "London"); gap()
    svc.hub_scan("P-1", "HUB-A"); gap()
    svc.out_for_delivery("P-1"); gap()
    svc.deliver("P-1"); gap()

    # P-4 fault (started early so its 12s window elapses within the demo):
    # out for delivery, then never delivered or returned -> timer violation.
    svc.register("P-4", "Rome"); gap()
    svc.hub_scan("P-4", "HUB-A"); gap()
    svc.out_for_delivery("P-4"); gap()

    # P-2 fault: out for delivery WITHOUT a hub scan -> rule 1 violation.
    svc.register("P-2", "Paris"); gap()
    svc.out_for_delivery("P-2"); gap()
    svc.deliver("P-2"); gap()

    # P-3 fault: delivered, then RE-ROUTED -> rule 2 violation.
    svc.register("P-3", "Berlin"); gap()
    svc.hub_scan("P-3", "HUB-B"); gap()
    svc.out_for_delivery("P-3"); gap()
    svc.deliver("P-3"); gap()
    svc.route_to("P-3", "HUB-C"); gap()

    # P-5 healthy: scanned, out for delivery, returned to sender in time.
    svc.register("P-5", "Madrid"); gap()
    svc.hub_scan("P-5", "HUB-B"); gap()
    svc.out_for_delivery("P-5"); gap()
    svc.return_to_sender("P-5")
    # P-4's window keeps counting; its timer fires ~12s after its dispatch.


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=None,
                    help="auto-shutdown after N seconds (default: wait for Ctrl-C)")
    ap.add_argument("--port", type=int, default=7007)
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "parcel_service.py")])
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    recorder = TraceRecorder(TRACE_PATH, clock=clock)

    svc = ParcelService(lambda e: source.push(dashboard.tap(recorder(e))),
                        clock=clock)

    # No terminal event: a delivered parcel must stay watched for rule 2, so
    # entities are reclaimed by quiescence TTL rather than a lifecycle end.
    engine = Engine(policies, terminal_event_types=set(),
                    grace=0.5, quiescence_ttl=120.0)

    url = dashboard.start(port=args.port)
    print("live monitor:", url)
    print("watch the policy cards and event feed there while traffic runs.")

    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    stop = threading.Event()
    driver = threading.Thread(target=drive, args=(svc, stop), daemon=True)
    driver.start()

    try:
        if args.seconds is not None:
            stop.wait(args.seconds)
        else:
            print("Ctrl-C to stop.")
            while not stop.is_set():
                stop.wait(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        recorder.close()
        print(f"\nrecorded trace: {TRACE_PATH}")
        print("replay it later with: "
              "python -m behave_rv --steps monitoring/steps.py "
              "--policy monitoring/policies/03_delivery_window.feature "
              f"--trace {TRACE_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
