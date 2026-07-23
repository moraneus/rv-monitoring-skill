"""Run the IoT fleet tracker LIVE with the monitor and the web dashboard.

    python demo.py               # serves ~30s, then shuts down cleanly
    python demo.py --seconds 90  # keep it up longer to click around

Standard live wiring (see the rv skill cheatsheet):

  traffic thread --push--> QueueSource --> Engine (its own thread)
                                              |
        browser <-- Dashboard (http) <-- sink (records under a lock)

The traffic thread emits events; the engine consumes on one thread; the
dashboard serves snapshots on a daemon thread. Nothing blocks the app. Every
event is teed into monitoring/traces/demo_session.jsonl for replay and for
`catalog diff --trace` liveness checks.

The seeded flows show, for each of the four rules, one entity that satisfies it
and one that breaks it.
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

from app.service import FleetService                            # noqa: E402
from steps import build_registry, load_policies                # noqa: E402

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

TERMINAL_TYPE = "device.retired"


def seed_traffic(svc: FleetService) -> None:
    """Drive both healthy and violating flows, paced so they are watchable."""
    def pause():
        time.sleep(0.25)

    # dev-1: HEALTHY - satisfies all three device rules.
    svc.provision("dev-1"); pause()
    svc.provision_passed("dev-1"); pause()
    svc.activate("dev-1"); pause()
    svc.act("dev-1", "ok"); pause()
    svc.act("dev-1", "ok"); pause()
    svc.quarantine("dev-1"); pause()
    svc.act("dev-1", "blocked"); pause()
    svc.wipe("dev-1"); pause()
    svc.retire("dev-1"); pause()

    # dev-2: VIOLATES rule 1 - activated straight after a FAILED check.
    svc.provision("dev-2"); pause()
    svc.provision_failed("dev-2"); pause()
    svc.activate("dev-2"); pause()
    svc.act("dev-2", "ok"); pause()
    svc.quarantine("dev-2"); pause()
    svc.wipe("dev-2"); pause()
    svc.retire("dev-2"); pause()

    # dev-3: VIOLATES rule 2 - a successful action AFTER quarantine.
    svc.provision("dev-3"); pause()
    svc.provision_passed("dev-3"); pause()
    svc.activate("dev-3"); pause()
    svc.act("dev-3", "ok"); pause()
    svc.quarantine("dev-3"); pause()
    svc.act("dev-3", "ok"); pause()
    svc.wipe("dev-3"); pause()
    svc.retire("dev-3"); pause()

    # dev-4: VIOLATES rule 3 - retired without ever being wiped.
    svc.provision("dev-4"); pause()
    svc.provision_passed("dev-4"); pause()
    svc.activate("dev-4"); pause()
    svc.act("dev-4", "ok"); pause()
    svc.retire("dev-4"); pause()

    # sensor-1: HEALTHY - only ok readings.
    svc.sensor_reading("sensor-1", "ok"); pause()
    svc.sensor_reading("sensor-1", "ok"); pause()
    svc.sensor_reading("sensor-1", "ok"); pause()

    # sensor-2: VIOLATES rule 4 - a non-ok reading.
    svc.sensor_reading("sensor-2", "ok"); pause()
    svc.sensor_reading("sensor-2", "ok"); pause()
    svc.sensor_reading("sensor-2", "error"); pause()

    # quarantine surge (rule 5): four devices quarantined AT ONCE. The app's
    # concurrent-quarantine count crosses 3 on the fourth, emitting the fleet
    # surge event - watch the "quarantine surge alert" card go violated. Each
    # device is otherwise healthy, so the surge is the only new alert.
    surge = ["dev-q1", "dev-q2", "dev-q3", "dev-q4"]
    for did in surge:
        svc.provision(did); pause()
        svc.provision_passed(did); pause()
        svc.activate(did); pause()
        svc.quarantine(did); pause()      # the 4th quarantine trips the alert
    for did in surge:
        svc.wipe(did); pause()
        svc.retire(did); pause()

    # rule 6 (since): once quarantined, only blocked rejections or decommission.
    # dev-r1 HEALTHY - after quarantine it only blocks, then is wiped/retired.
    svc.provision("dev-r1"); pause()
    svc.provision_passed("dev-r1"); pause()
    svc.activate("dev-r1"); pause()
    svc.act("dev-r1", "ok"); pause()
    svc.quarantine("dev-r1"); pause()
    svc.act("dev-r1", "blocked"); pause()
    svc.act("dev-r1", "blocked"); pause()
    svc.wipe("dev-r1"); pause()
    svc.retire("dev-r1"); pause()

    # dev-r2 VIOLATES ONLY rule 6 - a fresh provisioning after quarantine
    # (normal life resumed). Rules 1 and 2 do not catch this; the since rule
    # does. Watch its "quarantine is terminal" card go violated.
    svc.provision("dev-r2"); pause()
    svc.provision_passed("dev-r2"); pause()
    svc.activate("dev-r2"); pause()
    svc.act("dev-r2", "ok"); pause()
    svc.quarantine("dev-r2"); pause()
    svc.provision("dev-r2"); pause()     # forbidden after quarantine
    svc.wipe("dev-r2"); pause()
    svc.retire("dev-r2"); pause()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0,
                        help="how long to keep serving before shutting down")
    parser.add_argument("--port", type=int, default=7007)
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()                          # service-relative event time
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=ROOT / "monitoring/catalog.json",
                          app=[ROOT / "app/service.py"])   # both contract sides
    recorder = TraceRecorder(ROOT / "monitoring/traces/demo_session.jsonl")
    svc = FleetService(lambda e: source.push(dashboard.tap(recorder(e))),
                       clock=lambda: time.time() - start)

    url = dashboard.start(port=args.port)
    print("live monitor:", url)
    engine = Engine(policies, terminal_event_types={TERMINAL_TYPE}, grace=0.5)
    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=dashboard.sink), daemon=True)
    engine_thread.start()
    threading.Thread(target=lambda: seed_traffic(svc), daemon=True).start()

    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    source.close()
    engine_thread.join(timeout=5)
    dashboard.stop()
    recorder.close()
    print(f"done: {dashboard.state()['counts']['violations']} violation(s) "
          "shown on the dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
