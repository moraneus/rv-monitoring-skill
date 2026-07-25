"""Run the IoT fleet tracker LIVE with the monitor and the web dashboard.

    python app/demo.py                 # runs ~40s of scripted traffic, then idles
    python app/demo.py --seconds 20    # shorter window

Wiring (the standard behave-rv live shape):

  traffic thread --push--> QueueSource --> Engine (its own thread)
                                              |
        browser <-- Dashboard (http) <-- sink (records under a lock)

The dashboard shows, in the user's own words: every policy as a card with its
per-entity verdicts, the rendered explanation for each violation (the authored
scenario replayed with the real event values, failing step marked), the live
event feed, and the two-sided stability strip (are the step contracts AND the
app's emit sites still matching the committed catalog).

Both a HEALTHY and a VIOLATING flow are driven for each of the four rules so
you can watch verdicts land live.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from app.fleet import RETIRED_TYPE, FleetService                     # noqa: E402
from steps import build_registry, load_policies                     # noqa: E402

from behave_rv.dashboard import Dashboard                            # noqa: E402
from behave_rv.engine.loop import Engine                            # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder           # noqa: E402
from behave_rv.events.sources.subscription import QueueSource       # noqa: E402

PORT = 7204


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=40.0,
                        help="how long to keep serving before shutting down")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    # live-mode convention: service-relative event times keep traces readable.
    start = time.time()
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=ROOT / "monitoring" / "catalog.json",
                          app=[ROOT / "app" / "fleet.py"])   # both contract sides
    recorder = TraceRecorder(ROOT / "monitoring" / "traces" / "live_session.jsonl",
                             clock=lambda: time.time() - start)
    svc = FleetService(lambda e: source.push(dashboard.tap(recorder(e))),
                       clock=lambda: time.time() - start)

    url = dashboard.start(port=args.port)
    print("live monitor:", url)
    engine = Engine(policies, terminal_event_types={RETIRED_TYPE}, grace=0.5)
    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=dashboard.sink), daemon=True)
    engine_thread.start()

    def traffic() -> None:
        # ---- HEALTHY device: the full lifecycle, all device rules satisfied.
        svc.provision("D-1");                    time.sleep(0.4)
        svc.record_provision_check("D-1", True);  time.sleep(0.4)
        svc.activate("D-1");                     time.sleep(0.4)   # rule 01 ok
        svc.perform_action("D-1", "ok");         time.sleep(0.3)
        svc.perform_action("D-1", "ok");         time.sleep(0.3)
        svc.quarantine("D-1");                   time.sleep(0.4)
        svc.perform_action("D-1", "blocked");    time.sleep(0.3)   # rule 02 honored
        svc.wipe("D-1");                         time.sleep(0.4)   # rule 03 wiped...
        svc.retire("D-1");                       time.sleep(0.6)   # ...before retire

        # ---- HEALTHY sensor feed: only ok readings (rule 04 stays pending,
        #      never violated).
        svc.sensor_reading("S-1", "ok");         time.sleep(0.3)
        svc.sensor_reading("S-1", "ok");         time.sleep(0.3)
        svc.sensor_reading("S-1", "ok");         time.sleep(0.5)

        # ---- VIOLATION, rule 01: activated straight after a FAILED check.
        svc.provision("D-BAD1");                     time.sleep(0.4)
        svc.record_provision_check("D-BAD1", False);  time.sleep(0.4)
        svc.activate("D-BAD1");                      time.sleep(0.6)   # rule 01 VIOLATION

        # ---- VIOLATION, rule 02: a compromised device acts after quarantine.
        svc.provision("D-BAD2");                     time.sleep(0.4)
        svc.record_provision_check("D-BAD2", True);   time.sleep(0.3)
        svc.activate("D-BAD2");                      time.sleep(0.3)
        svc.quarantine("D-BAD2");                    time.sleep(0.4)
        svc.perform_action("D-BAD2", "ok");         time.sleep(0.6)   # rule 02 VIOLATION

        # ---- VIOLATION, rule 03: retired without ever being wiped.
        svc.provision("D-BAD3");                     time.sleep(0.4)
        svc.record_provision_check("D-BAD3", True);   time.sleep(0.3)
        svc.activate("D-BAD3");                      time.sleep(0.3)
        svc.retire("D-BAD3");                        time.sleep(0.6)   # rule 03 VIOLATION

        # ---- VIOLATION, rule 04: a sensor feed reports a non-ok reading.
        svc.sensor_reading("S-BAD", "ok");          time.sleep(0.4)
        svc.sensor_reading("S-BAD", "fault");       time.sleep(0.3)   # rule 04 VIOLATION

        # ---- VIOLATION, rule 05: a device reports an action but was never
        #      activated (D-1 shows the healthy case: activated before acting).
        svc.provision("D-BAD5");                     time.sleep(0.4)
        svc.record_provision_check("D-BAD5", True);   time.sleep(0.3)
        svc.perform_action("D-BAD5", "ok");         time.sleep(0.6)   # rule 05 VIOLATION

        # ---- VIOLATION, rule 06: a device is quarantined but was never
        #      activated (D-1 shows the healthy case: activated before quarantine).
        svc.provision("D-BAD6");                     time.sleep(0.4)
        svc.record_provision_check("D-BAD6", True);   time.sleep(0.3)
        svc.quarantine("D-BAD6");                    time.sleep(0.6)   # rule 06 VIOLATION

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
