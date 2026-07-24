"""Scripted demo mode - no browser needed.

Plays several honest hands and then injects corrupted event sequences, one per
table rule (the two the request names - a card dealt after stand, and a busted
hand settled as a win - plus a hand nobody finishes, a payout before
settlement, and a hand re-settled after it was already paid). Every event is
fed through the real engine; the console
prints each verdict with its rendered explanation, and (unless
``--no-dashboard``) the same run drives the live RV dashboard so the
violations show up there exactly as they would in the browser game.

    python demo.py                 # narrate + open the dashboard, stay up
    python demo.py --no-dashboard  # headless: just print the verdicts

The scripted traffic is the same one the replay gate pins
(``monitoring/replay_check.py``), so the demo and the gate agree by
construction.
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
from behave_rv.events.sources.subscription import QueueSource    # noqa: E402
from behave_rv.verdict.explain import explain_verdict            # noqa: E402

from app.game import EVENT_CLOSED                                # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402
from replay_check import simulate_traffic                        # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-dashboard", action="store_true",
                    help="run headless; print verdicts only")
    ap.add_argument("--dash-port", type=int, default=7102)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--pace", type=float, default=0.04,
                    help="seconds between injected events (visual pacing)")
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    source = QueueSource()
    dashboard = None
    dash_url = None
    if not args.no_dashboard:
        dashboard = Dashboard(policies, registry=registry,
                              catalog=str(ROOT / "monitoring" / "catalog.json"),
                              app=[str(ROOT / "app" / "game.py")])
        dash_url = dashboard.start(port=args.dash_port, host=args.host)
        print(f"RV dashboard: {dash_url}\n")

    verdicts_box: list = []
    engine = Engine(policies, terminal_event_types={EVENT_CLOSED})
    sink = dashboard.sink if dashboard else None

    def run_engine():
        verdicts_box.extend(engine.run(source, emit_pending=True, sink=sink))

    engine_thread = threading.Thread(target=run_engine, daemon=True)
    engine_thread.start()

    def emit(event):
        source.push(dashboard.tap(event) if dashboard else event)
        if args.pace:
            time.sleep(args.pace)

    print("Dealing honest hands, then injecting the cheats...\n")
    simulate_traffic(emit)
    source.close()
    engine_thread.join(timeout=10)

    verdicts = verdicts_box
    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    print("\n================  VERDICTS  ================")
    for v in verdicts:
        print(f"{v.verdict:9}  {str(v.entity_key):22}  {v.policy_id}")
    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s)\n")

    print("================  VIOLATIONS EXPLAINED  ================")
    for v in violations:
        policy = by_id[v.policy_id]
        print()
        print(explain_verdict(v, policy.authored_scenario,
                              policy.failing_step_index))

    if dashboard:
        print(f"\nDashboard still serving the results at {dash_url}")
        print("Ctrl-C to exit.")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nbye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
