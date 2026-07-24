"""Scripted tic-tac-toe demo -- no browser needed.

Plays six games through the REAL service and the REAL policies: two healthy
games and four that inject illegal events as corrupted moves (a double move by
the same player, a move after the win, a game abandoned before it finishes, and
a move for a game that never started). Every verdict is printed; each violation
is rendered as the authored Gherkin scenario with the failing step marked and
the deciding events bound in.

    python demo.py                 # batch: print verdicts + explanations, record a trace, exit
    python demo.py --serve         # also stream live into the behave-rv dashboard and hold it open
    python demo.py --serve --port 7104

The dashboard is the same one the browser game uses; --serve lets you watch the
violations land on the page in your own policy wording.
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

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource    # noqa: E402
from behave_rv.events.sources.subscription import QueueSource     # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder         # noqa: E402
from behave_rv.verdict.explain import explain_verdict             # noqa: E402

from app.game_service import TicTacToeService, ENDED_TYPE         # noqa: E402
from demo_script import Clock, run_script                         # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402

TRACE_PATH = ROOT / "monitoring" / "traces" / "demo_session.jsonl"
CATALOG_PATH = ROOT / "monitoring" / "catalog.json"
APP_PATH = ROOT / "app" / "game_service.py"


class PacingClock(Clock):
    """A clock that also sleeps on each tick, so a live run unfolds visibly."""

    def __init__(self, pace: float) -> None:
        super().__init__()
        self._pace = pace

    def tick(self, dt: float = 1.0) -> None:
        super().tick(dt)
        if self._pace:
            time.sleep(self._pace)


def _print_verdicts(verdicts, policies) -> None:
    by_id = {p.policy_id: p for p in policies}
    print(f"\n{'=' * 70}\nVERDICTS ({len(verdicts)} total)\n{'=' * 70}")
    for v in verdicts:
        gid = v.entity_key.get("game_id")
        print(f"  {v.verdict:9}  game {gid:3}  {v.policy_id}")
    violations = [v for v in verdicts if v.verdict == "violated"]
    print(f"\n{'=' * 70}\nEXPLANATIONS FOR {len(violations)} VIOLATION(S)\n{'=' * 70}")
    for v in violations:
        p = by_id[v.policy_id]
        print()
        print(explain_verdict(v, p.authored_scenario, p.failing_step_index))


def run_batch() -> int:
    registry = build_registry()
    policies = load_policies(registry)
    source = InProcessSource()
    clock = Clock()
    recorder = TraceRecorder(TRACE_PATH, clock=clock)
    service = TicTacToeService(lambda e: source.emit(recorder(e)), clock=clock)

    print("Playing 6 scripted games (2 healthy, 4 with injected corruption)...\n")
    for line in run_script(service, clock):
        print("  -", line)
    recorder.close()

    engine = Engine(policies, terminal_event_types={ENDED_TYPE})
    verdicts = engine.run(source, emit_pending=True)
    _print_verdicts(verdicts, policies)
    print(f"\nTrace recorded to {TRACE_PATH.relative_to(ROOT)}")
    return 0


def run_serve(port: int, host: str, pace: float) -> int:
    from behave_rv.dashboard import Dashboard

    registry = build_registry()
    policies = load_policies(registry)
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(CATALOG_PATH), app=[str(APP_PATH)])
    clock = PacingClock(pace)
    recorder = TraceRecorder(TRACE_PATH, clock=clock)
    service = TicTacToeService(
        lambda e: source.push(dashboard.tap(recorder(e))), clock=clock)

    dash_sink = dashboard.sink
    seen: list = []

    def tee(verdict) -> None:
        seen.append(verdict)
        gid = verdict.entity_key.get("game_id")
        print(f"  {verdict.verdict:9}  game {gid:3}  {verdict.policy_id}")
        dash_sink(verdict)

    engine = Engine(policies, terminal_event_types={ENDED_TYPE})
    threading.Thread(target=lambda: engine.run(source, sink=tee),
                     daemon=True).start()

    url = dashboard.start(port=port, host=host)
    print(f"\nlive monitor: {url}")
    print("Open it to watch the three violations land in your policy wording.\n")

    for line in run_script(service, clock):
        print("  -", line)
    time.sleep(1.0)
    recorder.close()
    print(f"\nTrace recorded to {TRACE_PATH.relative_to(ROOT)}")
    print("Dashboard is live. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        source.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Scripted tic-tac-toe RV demo")
    ap.add_argument("--serve", action="store_true",
                    help="stream live into the behave-rv dashboard and hold it open")
    ap.add_argument("--port", type=int, default=7104, help="dashboard port (--serve)")
    ap.add_argument("--host", default="127.0.0.1", help="dashboard host (--serve)")
    ap.add_argument("--pace", type=float, default=0.35,
                    help="seconds between actions in --serve mode")
    args = ap.parse_args()
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.serve:
        return run_serve(args.port, args.host, args.pace)
    return run_batch()


if __name__ == "__main__":
    raise SystemExit(main())
