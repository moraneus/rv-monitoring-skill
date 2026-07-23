"""Runnable live demo of the IoT fleet tracker under behave-rv monitoring.

    python demo.py            # live: opens the dashboard and holds it open
    python demo.py --once     # drain and exit (used by CI / smoke checks)
    python demo.py --pace 0.3 # seconds between actions in the live feed

It drives a mix of healthy and violating flows for all four rules through the
REAL FleetService, taps every event into the built-in dashboard, records the
stream to a replayable trace, and delivers verdicts to the dashboard live.

The dashboard (http://127.0.0.1:7007 by default) shows every policy as a card
with its per-entity verdicts, the rendered Gherkin explanation for each
violation, the live event feed, and the two-sided stability strip (are the
step contracts and the app's emit sites still in sync with the committed
catalog).
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

from app.service import FleetService                             # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402

TERMINAL_TYPES = {"device.retired"}
TRACE_PATH = ROOT / "monitoring" / "traces" / "demo_session.jsonl"


def drive(svc: FleetService, tick, pace: float) -> None:
    """Every seeded flow, healthy and violating, for all four rules."""

    def step(fn, *args):
        fn(*args)
        tick()                       # distinct, increasing event times
        if pace:
            time.sleep(pace)

    # attack wave: 4 devices quarantined while the fleet is otherwise clear.
    # The 4th quarantine crosses the threshold (>3) and fires ONE fleet surge
    # event -> the fleet-wide alert (rule 5). Run first so the concurrent count
    # is exactly these devices and the crossing is unambiguous.
    for d in ("attack-1", "attack-2", "attack-3", "attack-4"):
        step(svc.provision, d)
        step(svc.provision_ok, d)
        step(svc.quarantine, d)                # attack-4 -> surge

    # dev-clean: healthy end-to-end lifecycle (rules 1 and 3 satisfied).
    step(svc.provision, "dev-clean")
    step(svc.provision_ok, "dev-clean")
    step(svc.activate, "dev-clean")            # right after provision_ok
    step(svc.act, "dev-clean", "report-telemetry")
    step(svc.wipe, "dev-clean")
    step(svc.retire, "dev-clean")              # wiped before retire

    # dev-badact: activated without provision_ok immediately before (rule 1).
    step(svc.provision, "dev-badact")
    step(svc.activate, "dev-badact")

    # dev-quar-ok: quarantine, then only blocked rejections (rule 2 holds).
    step(svc.provision, "dev-quar-ok")
    step(svc.provision_ok, "dev-quar-ok")
    step(svc.activate, "dev-quar-ok")
    step(svc.quarantine, "dev-quar-ok")
    step(svc.blocked, "dev-quar-ok", "remote-exec")
    step(svc.blocked, "dev-quar-ok", "config-push")

    # dev-quar-bad: a normal action after quarantine (rule 2 violated).
    step(svc.provision, "dev-quar-bad")
    step(svc.provision_ok, "dev-quar-bad")
    step(svc.activate, "dev-quar-bad")
    step(svc.quarantine, "dev-quar-bad")
    step(svc.act, "dev-quar-bad", "report-telemetry")

    # dev-wipe-bad: retired without ever being wiped (rule 3 violated).
    step(svc.provision, "dev-wipe-bad")
    step(svc.provision_ok, "dev-wipe-bad")
    step(svc.activate, "dev-wipe-bad")
    step(svc.retire, "dev-wipe-bad")

    # dev-decom: the clean decommission path for a compromised device -
    # quarantine -> (blocked rejection) -> wipe -> retire. Under Option A every
    # post-quarantine event is "contained" (blocked or the wipe), so rule 2
    # stays green, rule 3 is satisfied (wiped before retire), and the device
    # legally leaves the fleet - all three cards green for dev-decom.
    step(svc.provision, "dev-decom")
    step(svc.provision_ok, "dev-decom")
    step(svc.activate, "dev-decom")
    step(svc.quarantine, "dev-decom")
    step(svc.blocked, "dev-decom", "remote-exec")   # a rejected attempt: allowed
    step(svc.wipe, "dev-decom")                      # decommission wipe: allowed
    step(svc.retire, "dev-decom")                    # leaves the fleet

    # sensor-ok: only ok readings (rule 4 holds).
    step(svc.sensor_reading, "sensor-ok", "ok", 21.4)
    step(svc.sensor_reading, "sensor-ok", "ok", 21.6)
    step(svc.sensor_reading, "sensor-ok", "ok", 21.5)

    # sensor-bad: a non-ok reading (rule 4 violated).
    step(svc.sensor_reading, "sensor-bad", "ok", 19.9)
    step(svc.sensor_reading, "sensor-bad", "ok", 20.1)
    step(svc.sensor_reading, "sensor-bad", "error", -1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true",
                    help="drain and exit instead of holding the dashboard open")
    ap.add_argument("--pace", type=float, default=0.15,
                    help="seconds between actions in the live feed")
    ap.add_argument("--port", type=int, default=7007)
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()                 # service-relative clock: readable times
    counter = {"n": 0.0}

    def clock():
        # wall-anchored but strictly increasing, so ordered actions never share
        # a timestamp even when paced faster than the clock's resolution
        return (time.time() - start) + counter["n"] * 1e-3

    def tick():
        counter["n"] += 1.0

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "service.py")])
    recorder = TraceRecorder(str(TRACE_PATH), clock=clock)
    svc = FleetService(lambda e: source.push(dashboard.tap(recorder(e))),
                       clock=clock)

    url = dashboard.start(port=args.port)
    print(f"live monitor: {url}")

    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    runner = threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink))
    runner.start()

    drive(svc, tick, pace=0.0 if args.once else args.pace)
    source.close()
    runner.join()
    recorder.close()

    print(f"event types seen: {sorted(engine.observed_types)}")
    print(f"verdicts delivered live: {engine.verdicts_delivered}")
    print(f"trace recorded:  {TRACE_PATH}")

    if args.once:
        dashboard.stop()
        return 0

    print(f"\nDashboard holding at {url} - Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
