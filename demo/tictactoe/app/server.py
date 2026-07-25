"""Interactive browser tic-tac-toe with the behave-rv dashboard alongside.

Two players share one keyboard/mouse: click a square to place the current
mark (X and O alternate automatically). Every action flows through the real
``GameService``, which emits events to a live behave-rv engine; the built-in
dashboard renders the three laws and their per-game verdicts as you play.

    python app/server.py            # game on :8804, dashboard on :7104

Both ports are configurable via --game-port / --dash-port. Ctrl+C stops
everything cleanly.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.dashboard import Dashboard                       # noqa: E402

from steps import build_registry, load_policies, OVER           # noqa: E402
from app.game import GameService, GameOver, IllegalMove         # noqa: E402

DASH_PORT = 7104


def build_page(dash_port: int) -> str:
    return PAGE.replace("__DASH_PORT__", str(dash_port))


class Handler(BaseHTTPRequestHandler):
    service: GameService = None       # set on the server instance
    dash_port: int = DASH_PORT

    def log_message(self, *args):     # quiet console
        return

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = build_page(self.dash_port).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/state":
            self._json(self.service.state())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/new":
            self.service.new_game()
            self._json(self.service.state())
        elif path == "/move":
            qs = parse_qs(parsed.query)
            try:
                cell = int(qs.get("cell", ["-1"])[0])
            except ValueError:
                cell = -1
            try:
                state = self.service.play(cell)
                self._json(state)
            except GameOver:
                self._json({**self.service.state(),
                            "error": "the game is already decided"})
            except IllegalMove as exc:
                self._json({**self.service.state(), "error": str(exc)})
        else:
            self._json({"error": "not found"}, 404)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-port", type=int, default=8804)
    parser.add_argument("--dash-port", type=int, default=DASH_PORT)
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "game.py")])
    recorder = TraceRecorder(str(ROOT / "monitoring" / "traces" / "live_session.jsonl"),
                             clock=clock)
    service = GameService(lambda e: source.push(dashboard.tap(recorder(e))),
                          clock=clock)

    engine = Engine(policies, terminal_event_types={OVER}, grace=0.5)
    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=dashboard.sink), daemon=True)
    engine_thread.start()

    dash_url = dashboard.start(port=args.dash_port)

    Handler.service = service
    Handler.dash_port = args.dash_port
    httpd = ThreadingHTTPServer(("127.0.0.1", args.game_port), Handler)

    game_url = f"http://127.0.0.1:{args.game_port}"
    print("=" * 60)
    print(f"  tic-tac-toe   {game_url}")
    print(f"  live monitor  {dash_url}")
    print("=" * 60)
    print("Two players, one keyboard: click a square to place the current")
    print("mark. Watch the three laws hold (and break) on the dashboard.")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        httpd.shutdown()
        source.close()
        recorder.close()
        dashboard.stop()
    return 0


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tic-Tac-Toe - runtime verified</title>
<style>
  * { box-sizing: border-box; }
  :root {
    --bg: #0e1117; --panel: #161b22; --line: #30363d; --ink: #e6edf3;
    --muted: #8b949e; --x: #58a6ff; --o: #f778ba; --ok: #3fb950; --bad: #f85149;
  }
  body { margin: 0; font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
         background: var(--bg); color: var(--ink); }
  header { padding: 16px 24px; border-bottom: 1px solid var(--line);
           display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
  header h1 { font-size: 18px; margin: 0; font-weight: 650; }
  header .sub { color: var(--muted); font-size: 13px; }
  .wrap { display: grid; grid-template-columns: 360px 1fr; gap: 0; min-height: calc(100vh - 58px); }
  @media (max-width: 820px) { .wrap { grid-template-columns: 1fr; } }
  .left { padding: 24px; border-right: 1px solid var(--line); }
  .status { font-size: 15px; margin: 0 0 14px; min-height: 22px; }
  .turn-x { color: var(--x); } .turn-o { color: var(--o); }
  .win { color: var(--ok); font-weight: 650; } .draw { color: var(--muted); font-weight: 650; }
  .board { display: grid; grid-template-columns: repeat(3, 104px);
           grid-template-rows: repeat(3, 104px); gap: 8px; }
  .cell { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
          font-size: 52px; font-weight: 700; cursor: pointer; color: var(--ink);
          display: flex; align-items: center; justify-content: center;
          transition: background .12s, transform .05s; }
  .cell:hover:not(.filled):not(:disabled) { background: #1c2330; }
  .cell:active:not(.filled) { transform: scale(0.97); }
  .cell.x { color: var(--x); } .cell.o { color: var(--o); }
  .cell.filled { cursor: default; }
  .controls { margin-top: 20px; display: flex; gap: 10px; align-items: center; }
  button.new { background: var(--x); color: #0b1220; border: 0; border-radius: 8px;
               padding: 9px 16px; font-size: 14px; font-weight: 650; cursor: pointer; }
  button.new:hover { filter: brightness(1.08); }
  .err { color: var(--bad); font-size: 13px; min-height: 18px; margin-top: 10px; }
  .laws { margin-top: 24px; font-size: 12.5px; color: var(--muted); line-height: 1.55; }
  .laws b { color: var(--ink); font-weight: 600; }
  .right { display: flex; flex-direction: column; }
  .right .bar { padding: 10px 16px; border-bottom: 1px solid var(--line);
                font-size: 13px; color: var(--muted); display: flex; gap: 12px; align-items: center; }
  .right .bar a { color: var(--x); text-decoration: none; }
  .right iframe { flex: 1; width: 100%; border: 0; background: #fff; }
</style>
</head>
<body>
<header>
  <h1>Tic-Tac-Toe</h1>
  <span class="sub">two players, one keyboard - every move checked at runtime by behave-rv</span>
</header>
<div class="wrap">
  <div class="left">
    <p class="status" id="status">X to move</p>
    <div class="board" id="board"></div>
    <div class="controls">
      <button class="new" id="new">New game</button>
      <span class="sub" id="gid"></span>
    </div>
    <div class="err" id="err"></div>
    <div class="laws">
      The monitor enforces, live:<br>
      <b>1.</b> players strictly alternate (no double move).<br>
      <b>2.</b> no move after a game is won or drawn.<br>
      <b>3.</b> every game that starts eventually finishes<br>
      &nbsp;&nbsp;&nbsp;(start a new game mid-play and watch law 3 flag the abandoned one).
    </div>
  </div>
  <div class="right">
    <div class="bar">
      <span>Runtime-verification dashboard</span>
      <a href="http://127.0.0.1:__DASH_PORT__" target="_blank" rel="noopener">open in a new tab &#8599;</a>
    </div>
    <iframe src="http://127.0.0.1:__DASH_PORT__" title="behave-rv dashboard"></iframe>
  </div>
</div>
<script>
const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const errEl = document.getElementById('err');
const gidEl = document.getElementById('gid');
let busy = false;

function render(state) {
  boardEl.innerHTML = '';
  const b = state.board || Array(9).fill('');
  for (let i = 0; i < 9; i++) {
    const c = document.createElement('button');
    c.className = 'cell' + (b[i] ? ' filled ' + b[i].toLowerCase() : '');
    c.textContent = b[i] || '';
    c.disabled = !!b[i] || state.decided;
    c.onclick = () => move(i);
    boardEl.appendChild(c);
  }
  gidEl.textContent = state.game_id ? state.game_id : '';
  if (state.decided && state.outcome === 'won') {
    statusEl.className = 'status win';
    statusEl.textContent = (state.winner) + ' wins!';
  } else if (state.decided && state.outcome === 'drawn') {
    statusEl.className = 'status draw';
    statusEl.textContent = "It's a draw.";
  } else {
    statusEl.className = 'status turn-' + (state.current || 'x').toLowerCase();
    statusEl.textContent = (state.current || 'X') + ' to move';
  }
}

async function move(i) {
  if (busy) return; busy = true; errEl.textContent = '';
  try {
    const r = await fetch('/move?cell=' + i, { method: 'POST' });
    const s = await r.json();
    if (s.error) errEl.textContent = s.error;
    render(s);
  } finally { busy = false; }
}

async function newGame() {
  errEl.textContent = '';
  const r = await fetch('/new', { method: 'POST' });
  render(await r.json());
}

document.getElementById('new').onclick = newGame;
(async () => {
  const r = await fetch('/state');
  const s = await r.json();
  if (!s.game_id) { await newGame(); } else { render(s); }
})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    raise SystemExit(main())
