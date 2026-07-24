"""Scripted demo - a few Snake games, no browser needed.

    python demo.py                 # play the scripts, print every verdict + why
    python demo.py --dashboard     # same, but also serve the live dashboard

It plays healthy games through the real engine and injects *corrupted* events -
the kind a buggy or tampered build could emit - to break each of the three
rules, so you see the monitor catch them both in the replay gate (the printed
verdicts here) and, with ``--dashboard``, on the live page. The exact same
scripted traffic is the exit-coded gate in ``monitoring/replay_check.py``.

The recorded trace (``monitoring/traces/demo_session.jsonl``) is what the
``catalog diff --trace`` liveness check reads.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.replay import ReplaySource, record_events  # noqa: E402
from behave_rv.verdict.explain import explain_verdict             # noqa: E402

from app.game import SnakeService                                 # noqa: E402
from replay_check import FakeClock, play_scenarios                # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402

TRACE = ROOT / "monitoring" / "traces" / "demo_session.jsonl"


def record_demo_trace() -> Path:
    events: list = []
    clock = FakeClock()
    service = SnakeService(events.append, clock=clock)
    play_scenarios(service, events.append, clock)
    record_events(str(TRACE), events, horizon=clock() + 0.001)
    return TRACE


def print_verdicts(policies) -> int:
    engine = Engine(policies, terminal_event_types=set(), grace=0.0)
    verdicts = engine.run(ReplaySource(str(TRACE)), emit_pending=True)
    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    print(f"\n{len(verdicts)} verdicts over the demo trace:\n")
    for v in verdicts:
        mark = {"violated": "X", "satisfied": ".", "pending": "~"}[v.verdict]
        print(f"  {mark} {v.verdict:9} {v.entity_key}  {v.policy_id}")

    print(f"\n--- {len(violations)} violation(s), each replayed as your scenario ---")
    for v in violations:
        p = by_id[v.policy_id]
        print()
        print(explain_verdict(v, p.authored_scenario, p.failing_step_index))
    return len(violations)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", action="store_true",
                    help="also serve the live dashboard and keep it up")
    ap.add_argument("--dashboard-port", type=int, default=7101)
    args = ap.parse_args()

    record_demo_trace()
    print(f"recorded {TRACE.relative_to(ROOT)}")

    registry = build_registry()
    policies = load_policies(registry)
    print_verdicts(policies)

    if args.dashboard:
        from behave_rv.dashboard import Dashboard
        import threading
        dashboard = Dashboard(policies, registry=registry,
                              catalog=str(ROOT / "monitoring" / "catalog.json"),
                              app=[str(ROOT / "app" / "game.py")])
        url = dashboard.start(port=args.dashboard_port)
        print(f"\nlive monitor: {url}  (Ctrl-C to stop)")

        def feed():
            engine = Engine(policies, terminal_event_types=set(), grace=0.0)
            for e in ReplaySource(str(TRACE)).events():
                dashboard.tap(e)
            engine.run(ReplaySource(str(TRACE)), sink=dashboard.sink)

        threading.Thread(target=feed, daemon=True).start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
