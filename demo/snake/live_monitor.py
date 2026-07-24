"""Run the Snake game live in the browser with the behave-rv monitor beside it.

    python live_monitor.py                       # game :8801, dashboard :7101
    python live_monitor.py --game-port 8801 --dashboard-port 7101

Open the game URL to play with the arrow keys; open the dashboard URL to watch
every policy as a card with its per-entity verdicts, the rendered explanation
for each violation, the live event feed, and the stability strip that shows the
code still matches the committed catalog. Play normally and every card stays
green; the corruption paths that turn cards red live in ``demo.py``.
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

from behave_rv.dashboard import Dashboard                         # noqa: E402
from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder         # noqa: E402
from behave_rv.events.sources.subscription import QueueSource     # noqa: E402

from app.game import SnakeService                                 # noqa: E402
from app.server import SnakeServer                                # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--game-port", type=int, default=8801)
    ap.add_argument("--dashboard-port", type=int, default=7101)
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    # One service-relative clock everywhere (game, recorder, verdicts) so wall
    # timers fire and traces stay readable.
    start = time.time()
    clock = lambda: time.time() - start

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "game.py")])
    recorder = TraceRecorder(str(ROOT / "monitoring" / "traces" / "live_session.jsonl"),
                             clock=clock)
    emit = lambda e: source.push(dashboard.tap(recorder(e)))

    service = SnakeService(emit, clock=clock)
    lock = threading.Lock()

    # game.over is NOT terminal (rule 1 must stay armed after a game ends);
    # dead games are reclaimed by the quiescence TTL instead.
    engine = Engine(policies, terminal_event_types=set(),
                    quiescence_ttl=300.0, grace=0.5)
    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    dash_url = dashboard.start(port=args.dashboard_port)
    game = SnakeServer(service, lock, host=args.host, port=args.game_port,
                       dashboard_url=dash_url)
    game_url = game.start()

    print("=" * 60)
    print(f"  play the game:   {game_url}")
    print(f"  live monitor:    {dash_url}")
    print("=" * 60)
    print("Ctrl-C to stop.")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        game.stop()
        source.close()
        recorder.close()      # writes the clock-horizon marker for replay
        print("\nstopped; trace at monitoring/traces/live_session.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
