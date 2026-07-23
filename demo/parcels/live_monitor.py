"""Run the parcel service live with the behave-rv dashboard.

    python live_monitor.py            # then open the printed URL

Drives a scripted stream of parcels through the REAL ParcelService (nothing
about its behaviour changes) while the monitor evaluates the three policies in
real time. Open the URL to watch, in your own words: every policy as a card
with its per-parcel verdicts, the authored scenario replayed with the failing
step marked for each violation, the live event feed, and the stability strip
comparing the running code to the committed catalog.

The whole session is teed to monitoring/traces/live_session.jsonl - a trace
you can replay later with:

    python -m behave_rv --steps monitoring/steps.py \
        --policy monitoring/policies/03_delivered_or_returned_within_12s.feature \
        --trace monitoring/traces/live_session.jsonl

Ctrl-C to stop.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "monitoring"))
sys.path.insert(0, str(ROOT))

from behave_rv.dashboard import Dashboard                        # noqa: E402
from behave_rv.engine.loop import Engine                         # noqa: E402
from behave_rv.events.sources.subscription import QueueSource    # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder        # noqa: E402

from app.parcel_service import ParcelService                     # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402

STEP_DELAY = 1.2   # seconds between scripted actions, so the feed is watchable


def script(svc: ParcelService) -> None:
    """A watchable live stream: healthy parcels plus one instance of each of
    the three faults (unscanned dispatch, reroute after delivery, delivery
    that never resolves within the deadline)."""
    steps = [
        lambda: svc.register("P-1", "Berlin"),
        lambda: svc.register("P-2", "Munich"),
        lambda: svc.register("P-3", "Hamburg"),     # will skip its hub scan
        lambda: svc.register("P-4", "Cologne"),     # will be rerouted post-delivery
        lambda: svc.register("P-5", "Bremen"),      # will stall out for delivery
        lambda: svc.hub_scan("P-1", "HUB-A"),
        lambda: svc.hub_scan("P-2", "HUB-B"),
        lambda: svc.hub_scan("P-4", "HUB-C"),
        lambda: svc.hub_scan("P-5", "HUB-A"),
        lambda: svc.out_for_delivery("P-1"),
        lambda: svc.out_for_delivery("P-2"),
        lambda: svc.out_for_delivery("P-3"),        # VIOLATES rule 1 (no scan)
        lambda: svc.out_for_delivery("P-4"),
        lambda: svc.out_for_delivery("P-5"),        # starts rule 3's 12s clock
        lambda: svc.deliver("P-1"),
        lambda: svc.return_to_sender("P-2"),
        lambda: svc.deliver("P-3"),
        lambda: svc.deliver("P-4"),
        lambda: svc.route_to("P-4", "HUB-D"),        # VIOLATES rule 2 (reroute)
    ]
    for step in steps:
        step()
        time.sleep(STEP_DELAY)
    # P-5 never gets delivered: rule 3's within-timer fires on the wall clock
    # during this quiet period (deadline is 12s after P-5 went out for delivery).


def main() -> int:
    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()                              # service-relative clock
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog="monitoring/catalog.json",
                          app=["app/parcel_service.py"])
    recorder = TraceRecorder("monitoring/traces/live_session.jsonl")

    svc = ParcelService(lambda e: source.push(dashboard.tap(recorder(e))),
                        clock=lambda: time.time() - start)

    # No terminal event: rule 2 must keep watching for a post-delivery reroute,
    # so delivery does not retire the parcel. Dormant parcels free by TTL.
    engine = Engine(policies, quiescence_ttl=300.0)
    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    url = dashboard.start(port=7007)
    print("live monitor:", url)
    print("watch the three policy cards; a trace is being recorded to "
          "monitoring/traces/live_session.jsonl")

    script(svc)

    print("\nscripted traffic done; the monitor stays live (rule 3's timer is "
          "still counting down for P-5). Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        source.close()
        recorder.close()
        print("\nstopped. trace saved to monitoring/traces/live_session.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
