"""Scripted demo - no browser needed.

Plays a handful of Snake games through the real engine and injects the four
rule-breaking corruptions as raw stream events, feeding a LIVE behave-rv
dashboard so you can watch the policy cards turn red, then prints every verdict
with its rendered explanation. The SAME traffic runs under the exit-coded gate
(``monitoring/replay_check.py``); this view adds the live dashboard.

    python demo.py [--dash-port 7101] [--no-dashboard]

The dashboard stays up for a few seconds after the run so you can read the
violations; press Ctrl-C to exit sooner.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.traffic import play                                    # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dash-port", type=int, default=7101)
    ap.add_argument("--no-dashboard", action="store_true")
    ap.add_argument("--linger", type=float, default=8.0,
                    help="seconds to keep the dashboard up after the run")
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start
    source = QueueSource()

    dashboard = None
    dash_url = "(dashboard disabled)"
    if not args.no_dashboard:
        dashboard = Dashboard(policies, registry=registry,
                              catalog=str(ROOT / "monitoring" / "catalog.json"),
                              app=[str(ROOT / "app" / "game.py"),
                                   str(ROOT / "app" / "traffic.py")])
        dash_url = dashboard.start(port=args.dash_port)

    recorder = TraceRecorder(str(ROOT / "monitoring" / "traces" / "demo_session.jsonl"),
                             clock=clock)

    def emit(event):
        source.push(dashboard.tap(recorder(event)) if dashboard else recorder(event))

    # Live-mode timing: advance() sleeps in real wall time so the 2-second
    # `within` deadline actually matures on the wall clock (service-relative
    # clock, so event times stay small and the timer fires).
    def advance(dt):
        time.sleep(dt)

    engine = Engine(policies, terminal_event_types=set(), grace=0.25)

    # When a sink is passed, the engine delivers verdicts to it rather than
    # through the return value - so collect them here AND forward to the live
    # dashboard.
    verdicts_out: list = []

    def sink(verdict):
        verdicts_out.append(verdict)
        if dashboard:
            dashboard.sink(verdict)

    import threading
    t = threading.Thread(
        target=lambda: engine.run(source, emit_pending=True, sink=sink),
        daemon=True)
    t.start()

    print(f"live monitor:   {dash_url}\n")
    print("Playing scripted games (healthy + corrupted)...\n")
    notes = play(emit, clock, advance)
    for gid, what, rule in notes:
        print(f"  {gid:22}  {what}   [{rule}]")

    time.sleep(0.6)               # let the last verdicts land
    source.close()
    recorder.close()
    t.join(timeout=5)

    verdicts = verdicts_out
    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s):\n")
    for v in violations:
        policy = by_id[v.policy_id]
        print(explain_verdict(v, policy.authored_scenario,
                              policy.failing_step_index))
        print()

    if dashboard:
        print(f"Dashboard live at {dash_url} for {args.linger:.0f}s "
              "(Ctrl-C to exit now).")
        try:
            time.sleep(args.linger)
        except KeyboardInterrupt:
            pass
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
