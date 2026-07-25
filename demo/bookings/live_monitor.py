"""Run the class-bookings app LIVE with the monitor and the web dashboard.

    python live_monitor.py                 # serves ~40s of scripted traffic
    python live_monitor.py --seconds 120   # keep serving longer

Open the printed URL to watch, in the owner's own words:
  * every policy as a card with its per-booking verdicts,
  * the rendered explanation for each violation (the authored scenario
    replayed with the real booking's events, failing step marked),
  * the live event feed, and
  * the stability strip: whether the running code still matches the committed
    catalog (both the step contracts and the app's emit sites).

Wiring:  app thread --push--> QueueSource --> Engine (own thread)
                                                  |
                     browser <-- Dashboard(http) <-- sink

There is NO terminal event type and a 60s quiescence TTL, so each booking is
watched for 60s past its last activity (standing in for "until end of day").
That window is what lets policy 01 catch a check-in that lands after a cancel.
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

from app.booking_service import BookingService                     # noqa: E402
from steps import build_registry, load_policies                    # noqa: E402

from behave_rv.dashboard import Dashboard                          # noqa: E402
from behave_rv.engine.loop import Engine                           # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder          # noqa: E402
from behave_rv.events.sources.subscription import QueueSource      # noqa: E402

DASHBOARD_PORT = 7203
QUIESCENCE_TTL = 60.0

# "Loud" policies would page someone; the rest just log. The monitoring is
# identical - this only routes a prominent alert line when a loud one violates.
LOUD_POLICIES = {
    "a cancelled booking is never checked in",
    "a promoted booking is confirmed or cancelled within 15 seconds",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=40.0)
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=ROOT / "monitoring/catalog.json",
                          app=[ROOT / "app/booking_service.py"])

    trace_path = ROOT / "monitoring/traces/live_session.jsonl"
    trace_path.parent.mkdir(exist_ok=True)
    trace_path.unlink(missing_ok=True)   # TraceRecorder appends; start fresh
    recorder = TraceRecorder(trace_path, clock=lambda: time.time() - start)

    svc = BookingService(lambda e: source.push(dashboard.tap(recorder(e))),
                         clock=lambda: time.time() - start)

    def sink(verdict):
        dashboard.sink(verdict)
        if verdict.verdict == "violated" and verdict.policy_id in LOUD_POLICIES:
            print(f"  ALERT (would page): {verdict.policy_id} "
                  f"{verdict.entity_key}")

    # grace stays BELOW the 15s deadline so a legitimately-answered promotion
    # is never read as a false timeout on the live wall clock.
    engine = Engine(policies, terminal_event_types=set(),
                    grace=0.5, quiescence_ttl=QUIESCENCE_TTL)
    url = dashboard.start(port=DASHBOARD_PORT)
    print("live monitor:", url)
    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=sink), daemon=True)
    engine_thread.start()

    def traffic():
        # a healthy booking, start to finish
        svc.reserve("B-1001"); time.sleep(0.4)
        svc.confirm("B-1001"); time.sleep(0.4)
        svc.check_in("B-1001"); time.sleep(0.3)
        svc.mark_attended("B-1001"); time.sleep(0.4)

        # a healthy waitlist promotion, answered in time
        svc.reserve("B-1002"); time.sleep(0.3)
        svc.waitlist("B-1002"); time.sleep(0.4)
        svc.promote("B-1002"); time.sleep(0.5)
        svc.confirm("B-1002"); time.sleep(0.3)      # well under 15s
        svc.check_in("B-1002"); time.sleep(0.3)
        svc.mark_attended("B-1002"); time.sleep(0.4)

        # THE #1 NIGHTMARE: cancelled, then checked in anyway (loud)
        svc.reserve("B-1003"); time.sleep(0.3)
        svc.confirm("B-1003"); time.sleep(0.3)
        svc.cancel("B-1003"); time.sleep(0.6)
        svc.check_in("B-1003"); time.sleep(0.5)     # -> violates 01, pages

        # a promotion left hanging: the 15s timer fires on silence (loud)
        svc.reserve("B-1004"); time.sleep(0.3)
        svc.waitlist("B-1004"); time.sleep(0.3)
        svc.promote("B-1004")                       # then nothing -> 05 timeout

    threading.Thread(target=traffic, daemon=True).start()

    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    source.close()
    engine_thread.join(timeout=5)
    dashboard.stop()
    recorder.close()
    print(f"done: {engine.verdicts_delivered} verdicts delivered "
          f"({dashboard.state()['counts']['violations']} violations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
