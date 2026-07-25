"""Run the payment tracker live, under behave-rv, with the web dashboard.

    python demo.py                # run the scripted flows, then exit
    python demo.py --serve        # run them, then keep the dashboard up to watch

What you see at the dashboard URL (default http://127.0.0.1:7205):
  * every policy as a card with its per-entity verdicts (satisfied/violated/pending),
  * the rendered explanation for each violation - your own scenario replayed
    with the real event values and the failing step marked,
  * the live event feed,
  * a stability strip: whether the running code still matches the committed
    catalog, on BOTH sides (the step predicates and the app's emit sites).

The flows are driven on a real (service-relative) wall clock, as a live source
must be. The 20-second deadline is your "demo scale for 5 days"; the abandoned
payment's rule-3 timeout fires on the wall clock about 20s in.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from behave_rv.dashboard import Dashboard                        # noqa: E402
from behave_rv.engine.loop import Engine                         # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource    # noqa: E402

from steps import build_registry, load_policies                  # noqa: E402
from app.service import PaymentService                            # noqa: E402

PORT = 7205
TERMINAL_TYPES = {"payment.closed"}
DEADLINE_SECONDS = 20.0
STEP_PAUSE = 0.4          # real seconds between actions (a watchable tempo)
GRACE = 1.0              # reorder window; in-process has no lag, so keep it small


def main(serve: bool) -> int:
    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start        # one service-relative clock

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog="monitoring/catalog.json",
                          app=["app/service.py"])
    recorder = TraceRecorder("monitoring/traces/live_session.jsonl", clock=clock)
    svc = PaymentService(lambda e: source.push(dashboard.tap(recorder(e))), clock)

    url = dashboard.start(port=PORT)
    print(f"live monitor: {url}")
    print("driving payment flows...\n")

    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=GRACE)
    thread = threading.Thread(target=engine.run,
                              kwargs={"source": source, "sink": dashboard.sink},
                              daemon=True)
    thread.start()

    def step(msg, fn):
        print(" ", msg)
        fn()
        time.sleep(STEP_PAUSE)

    # P-3003: capture and then abandon it -- its 20s deadline (rule 3) will fire
    # on the wall clock while the other flows run and during the final wait.
    step("P-3003 authorized", lambda: svc.authorize("P-3003"))
    step("P-3003 captured  (now abandoned; rule 3 will time out ~20s)",
         lambda: svc.capture("P-3003"))

    # P-1001: HEALTHY -- a clean, never-disputed payment. Rule 2 only binds to
    # disputed closes, so a plain close is free; all three rules stay green.
    step("P-1001 authorized", lambda: svc.authorize("P-1001"))
    step("P-1001 captured", lambda: svc.capture("P-1001"))
    step("P-1001 closed    (clean close, no dispute -> all green)",
         lambda: svc.close("P-1001"))

    # P-2002: HEALTHY -- a disputed payment run through the full resolution
    # path. The team's investigate/refund/close is exactly what should happen;
    # the customer's re-capture attempt is refused by the frozen guard (a
    # rejection event, not a violation). All three rules stay green.
    step("P-2002 authorized", lambda: svc.authorize("P-2002"))
    step("P-2002 captured", lambda: svc.capture("P-2002"))
    step("P-2002 disputed  (payment frozen)", lambda: svc.dispute("P-2002"))
    step("P-2002 re-capture attempted -> frozen rejection (guard works)",
         lambda: svc.attempt_customer_action("P-2002", "recapture"))
    step("P-2002 investigated  (team resolution, allowed)",
         lambda: svc.investigate("P-2002"))
    step("P-2002 refunded", lambda: svc.refund("P-2002"))
    step("P-2002 closed    (refunded first -> rule 2 satisfied)",
         lambda: svc.close("P-2002"))

    # P-4004: VIOLATION -- a frozen payment re-captured through a guard bypass.
    # (capture() called directly simulates the bug rule 1 exists to catch.)
    step("P-4004 authorized", lambda: svc.authorize("P-4004"))
    step("P-4004 captured", lambda: svc.capture("P-4004"))
    step("P-4004 disputed  (payment frozen)", lambda: svc.dispute("P-4004"))
    step("P-4004 RE-CAPTURED while frozen -> rule 1 violation",
         lambda: svc.capture("P-4004"))

    # P-5005: VIOLATION -- a disputed payment closed with no refund -> rule 2.
    step("P-5005 authorized", lambda: svc.authorize("P-5005"))
    step("P-5005 captured", lambda: svc.capture("P-5005"))
    step("P-5005 disputed  (payment frozen)", lambda: svc.dispute("P-5005"))
    step("P-5005 closed    (disputed close, no refund -> rule 2 violation)",
         lambda: svc.close("P-5005"))

    # Wait out P-3003's deadline so the rule-3 timeout fires live. The wall
    # fire matures at the deadline plus the reorder grace; keep the stream open
    # comfortably past that (event time tracks this service-relative clock).
    fire_by = DEADLINE_SECONDS + GRACE + 2.0
    print(f"\n  keeping the stream open until ~{fire_by:.0f}s so P-3003's "
          "20s deadline fires live...")
    while clock() < fire_by:
        time.sleep(0.5)

    source.close()
    thread.join(timeout=5.0)
    recorder.close()

    print("\nflows complete. dashboard summary:")
    st = dashboard.state()
    print(f"  events={st['counts']['events']}  verdicts={st['counts']['verdicts']}"
          f"  violations={st['counts']['violations']}")
    print(f"  contract check: {st['stability']['status']}")

    if serve:
        print(f"\nserving the live view at {url} - Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
    dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(serve="--serve" in sys.argv[1:]))
