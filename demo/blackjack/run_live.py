"""Live entry point: play Blackjack in the browser while behave-rv verifies the
table rules on its dashboard, over the real event stream.

    python run_live.py [--game-port 8802] [--dash-port 7102]

Opens two servers:
  * the game UI  (default http://127.0.0.1:8802)
  * the RV dashboard (default http://127.0.0.1:7102)

Events flow game -> QueueSource -> engine (own thread) -> dashboard.sink, and
are teed through the dashboard's live feed and a TraceRecorder. A
service-relative clock (time.time() - start) keeps event times small so
`within` deadlines fire on wall time for a quiet table.
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
from behave_rv.events.sources.replay import TraceRecorder        # noqa: E402

from app.game import BlackjackGame, EVENT_CLOSED                 # noqa: E402
from app.server import make_server                               # noqa: E402
from steps import build_registry, load_policies                 # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-port", type=int, default=8802)
    ap.add_argument("--dash-port", type=int, default=7102)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "game.py")])

    start = time.time()
    clock = lambda: time.time() - start
    trace_path = ROOT / "monitoring" / "traces" / "live_session.jsonl"
    recorder = TraceRecorder(str(trace_path), clock=clock)

    def emit(event):
        source.push(dashboard.tap(recorder(event)))

    game = BlackjackGame(emit, clock=clock)

    engine = Engine(policies, terminal_event_types={EVENT_CLOSED})
    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=dashboard.sink), daemon=True)
    engine_thread.start()

    dash_url = dashboard.start(port=args.dash_port, host=args.host)
    game_server = make_server(game, args.host, args.game_port, dash_url)
    game_url = f"http://{args.host}:{args.game_port}"

    print("=" * 60)
    print(f"  Blackjack table : {game_url}")
    print(f"  RV dashboard    : {dash_url}")
    print("=" * 60)
    print("Play in the browser; watch the four rules verify live. Ctrl-C to stop.")

    server_thread = threading.Thread(target=game_server.serve_forever,
                                     daemon=True)
    server_thread.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        game_server.shutdown()
        source.close()
        recorder.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
