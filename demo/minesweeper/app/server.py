"""The live Minesweeper: a browser board on one port, the behave-rv dashboard
on another, wired to the same event stream the game emits as you play.

Run it:

    python app/server.py [--game-port 8803] [--dash-port 7103]

Open the game URL it prints, and the dashboard URL beside it. Every click you
make emits events; the engine (running in its own thread) decides verdicts and
the dashboard shows each policy as a live card with its per-entity verdicts and
rendered explanations. Stdlib only - the UI is inline HTML/JS, no CDNs.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "monitoring"))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.dashboard import Dashboard                       # noqa: E402

from steps import build_registry, load_policies                 # noqa: E402
from app.game import MinesweeperGame                            # noqa: E402

TERMINAL_TYPES = {"game.done"}
TRACE_PATH = str(Path(__file__).resolve().parents[1] / "monitoring" / "traces" / "live_session.jsonl")


class MonotonicClock:
    """Wall-time event clock that never repeats a value, so ordered emissions
    always carry distinct, increasing timestamps. Tracks wall rate (live-safe):
    it only nudges forward by a hair when two emits share an instant."""

    def __init__(self):
        self._start = time.time()
        self._last = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            now = time.time() - self._start
            if now <= self._last:
                now = self._last + 1e-4
            self._last = now
            return now


class GameHost:
    """Owns the current board and the monitoring wiring. One lock serialises a
    move and its emissions so the event order the monitor sees matches play."""

    def __init__(self, dash_port: int):
        self._lock = threading.Lock()
        self._clock = MonotonicClock()
        self._counter = 0

        registry = build_registry()
        self._policies = load_policies(registry)
        self._source = QueueSource()
        self._recorder = TraceRecorder(TRACE_PATH, clock=self._clock)
        self._dashboard = Dashboard(
            self._policies, registry=registry,
            catalog=str(Path(__file__).resolve().parents[1] / "monitoring" / "catalog.json"),
            app=[str(Path(__file__).resolve().parent / "game.py")],
        )
        self.dash_url = self._dashboard.start(port=dash_port)

        self._engine = Engine(self._policies, terminal_event_types=TERMINAL_TYPES,
                              grace=0.2, quiescence_ttl=3600.0)
        self._thread = threading.Thread(
            target=self._engine.run,
            args=(self._source,), kwargs={"sink": self._dashboard.sink},
            daemon=True)
        self._thread.start()

        self.game = self._new_game()

    def _emit(self, event):
        # tee to the trace file, register on the dashboard, feed the engine.
        self._source.push(self._dashboard.tap(self._recorder(event)))

    def _new_game(self) -> MinesweeperGame:
        self._counter += 1
        return MinesweeperGame(f"game-{self._counter}", self._emit, self._clock)

    def new_game(self) -> dict:
        with self._lock:
            self.game = self._new_game()
            return self.game.view()

    def reveal(self, r: int, c: int) -> dict:
        with self._lock:
            self.game.reveal(r, c)
            return self.game.view()

    def flag(self, r: int, c: int) -> dict:
        with self._lock:
            self.game.toggle_flag(r, c)
            return self.game.view()

    def state(self) -> dict:
        with self._lock:
            return self.game.view()

    def shutdown(self):
        self._source.close()
        self._recorder.close()
        self._dashboard.stop()


def build_page(dash_url: str) -> bytes:
    return PAGE.replace("__DASH_URL__", dash_url).encode("utf-8")


def make_handler(host: GameHost, dash_url: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body: bytes, ctype="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj):
            self._send(json.dumps(obj).encode("utf-8"))

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(build_page(dash_url), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._json(host.state())
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/api/new":
                self._json(host.new_game())
            elif self.path == "/api/reveal":
                b = self._read_body()
                self._json(host.reveal(int(b["row"]), int(b["col"])))
            elif self.path == "/api/flag":
                b = self._read_body()
                self._json(host.flag(int(b["row"]), int(b["col"])))
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minesweeper - monitored</title>
<style>
  :root {
    --bg:#0f1220; --panel:#1a1e33; --edge:#2b3152; --ink:#e7e9f5; --muted:#9aa0c3;
    --unrev:#2a2f4f; --unrev2:#333a63; --rev:#141830; --flag:#ffbd4a; --boom:#ff4d5e;
    --accent:#5b8cff;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:radial-gradient(1200px 700px at 70% -10%, #1c2450, transparent), var(--bg);
         color:var(--ink); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .wrap { max-width:760px; margin:0 auto; padding:28px 20px 60px; }
  h1 { font-size:26px; margin:0 0 4px; letter-spacing:.3px; }
  .sub { color:var(--muted); margin:0 0 22px; }
  .sub a { color:var(--accent); text-decoration:none; }
  .sub a:hover { text-decoration:underline; }
  .hud { display:flex; gap:14px; align-items:center; margin-bottom:16px; flex-wrap:wrap; }
  .chip { background:var(--panel); border:1px solid var(--edge); border-radius:12px;
          padding:8px 14px; font-variant-numeric:tabular-nums; }
  .chip b { color:var(--ink); } .chip span { color:var(--muted); }
  button.new { margin-left:auto; background:var(--accent); color:#08122e; border:0;
          border-radius:12px; padding:10px 18px; font-weight:650; cursor:pointer; }
  button.new:hover { filter:brightness(1.08); }
  .status { font-weight:650; padding:8px 14px; border-radius:12px; border:1px solid var(--edge); }
  .status.playing { color:var(--muted); }
  .status.won { color:#4ade80; border-color:#20613f; background:#10281c; }
  .status.lost { color:var(--boom); border-color:#5f2230; background:#2a1017; }
  .board { display:grid; grid-template-columns:repeat(8, 1fr); gap:6px;
           background:var(--panel); border:1px solid var(--edge); border-radius:16px; padding:12px; }
  .cell { aspect-ratio:1/1; border-radius:9px; border:1px solid var(--edge);
          background:linear-gradient(180deg,var(--unrev2),var(--unrev));
          display:flex; align-items:center; justify-content:center;
          font-weight:750; font-size:19px; cursor:pointer; user-select:none;
          transition:transform .05s, background .1s; }
  .cell:hover { transform:translateY(-1px); }
  .cell.rev { background:var(--rev); border-color:#20263f; cursor:default; box-shadow:inset 0 0 0 1px #171b30; }
  .cell.rev:hover { transform:none; }
  .cell.flag { color:var(--flag); }
  .cell.mine { background:linear-gradient(180deg,#3a1420,#2a0e17); border-color:#5f2230; color:var(--boom); }
  .n1{color:#7aa2ff}.n2{color:#4ade80}.n3{color:#ff8f6b}.n4{color:#b98cff}
  .n5{color:#ffbd4a}.n6{color:#54d6d6}.n7{color:#e7e9f5}.n8{color:#9aa0c3}
  .hint { color:var(--muted); font-size:13px; margin-top:16px; }
  kbd { background:#0c1024; border:1px solid var(--edge); border-radius:6px; padding:1px 7px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Minesweeper</h1>
  <p class="sub">8x8, 10 mines. Left-click reveals, right-click flags. Every move is
     checked live by <a href="__DASH_URL__" target="_blank">the behave-rv monitor &rarr;</a></p>
  <div class="hud">
    <div class="chip"><span>mines</span> <b id="mines">10</b></div>
    <div class="chip"><span>flags</span> <b id="flags">0</b></div>
    <div id="status" class="status playing">playing</div>
    <button class="new" onclick="newGame()">New game</button>
  </div>
  <div id="board" class="board"></div>
  <p class="hint">Rules the monitor enforces: no reveal after a mine explodes &middot;
     no square revealed twice &middot; flags never exceed the mine count.
     Open <a href="__DASH_URL__" target="_blank">the dashboard</a> in a second window and watch the cards while you play.</p>
</div>
<script>
const boardEl = document.getElementById('board');
const NUMS = ['','n1','n2','n3','n4','n5','n6','n7','n8'];

function render(view) {
  document.getElementById('flags').textContent = view.flags;
  document.getElementById('mines').textContent = view.mines;
  const st = document.getElementById('status');
  st.className = 'status ' + view.status;
  st.textContent = view.status === 'won' ? 'cleared!' : view.status === 'lost' ? 'boom' : 'playing';
  boardEl.innerHTML = '';
  for (const cell of view.cells) {
    const d = document.createElement('div');
    d.className = 'cell';
    if (cell.revealed) {
      d.classList.add('rev');
      if (cell.mine) { d.classList.add('mine'); d.textContent = '✹'; }
      else if (cell.count) { d.classList.add(NUMS[cell.count]); d.textContent = cell.count; }
    } else if (cell.mine) {
      d.classList.add('mine'); d.textContent = '✹';
    } else if (cell.flagged) {
      d.classList.add('flag'); d.textContent = '⚑';
    }
    d.oncontextmenu = (e) => { e.preventDefault(); act('/api/flag', cell.row, cell.col); };
    d.onclick = () => act('/api/reveal', cell.row, cell.col);
    boardEl.appendChild(d);
  }
}

async function act(path, row, col) {
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                              body: JSON.stringify({row, col})});
  render(await r.json());
}
async function newGame() {
  const r = await fetch('/api/new', {method:'POST'});
  render(await r.json());
}
async function load() {
  const r = await fetch('/api/state');
  render(await r.json());
}
load();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-port", type=int, default=8803)
    parser.add_argument("--dash-port", type=int, default=7103)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    host = GameHost(args.dash_port)
    server = ThreadingHTTPServer((args.host, args.game_port),
                                 make_handler(host, host.dash_url))
    game_url = f"http://{args.host}:{server.server_address[1]}"
    print(f"minesweeper : {game_url}")
    print(f"live monitor: {host.dash_url}")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        host.shutdown()
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
