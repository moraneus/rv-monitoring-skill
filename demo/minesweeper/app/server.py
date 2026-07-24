"""Browser Minesweeper with a live behave-rv monitor alongside.

Serves the game UI (stdlib http.server, inline HTML/CSS/JS, no CDNs) on one
port and the behave-rv dashboard on another. Every honest game action flows
through the real ``Minesweeper`` engine, whose events are teed into the
dashboard, recorded to a trace, and delivered to the monitoring engine
running in a background thread.

The three "inject cheat" buttons construct CORRUPTED events directly and push
them onto the same stream, bypassing the game's own guards - exactly what a
compromised or out-of-band component would do. The monitor, which trusts only
the event stream, catches each one and you watch the verdict turn red on the
dashboard live.

    python app/server.py [--game-port 8803] [--dash-port 7103]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.minesweeper import (                                   # noqa: E402
    Minesweeper, MonotonicClock, CELL_REVEAL, CELL_REVEALED, MINE_EXPLODED,
    FLAG_PLACED, SOURCE,
)
from steps import build_registry, load_policies                # noqa: E402


class Live:
    """Holds the monitor wiring and the current game."""

    def __init__(self, dash_port: int):
        self.clock = MonotonicClock()
        self.source = QueueSource()
        self.registry = build_registry()
        self.policies = load_policies(self.registry)
        self.dashboard = Dashboard(
            self.policies,
            registry=self.registry,
            catalog=str(ROOT / "monitoring" / "catalog.json"),
            app=[str(ROOT / "app" / "minesweeper.py")],
        )
        traces = ROOT / "monitoring" / "traces"
        traces.mkdir(exist_ok=True)
        # TraceRecorder appends; a live trace represents one session, and game
        # ids restart per server run, so start the file fresh to keep it
        # replayable without phantom cross-session duplicates.
        live_trace = traces / "live_session.jsonl"
        live_trace.unlink(missing_ok=True)
        self.recorder = TraceRecorder(str(live_trace), clock=self.clock)
        # grace is the event-time reorder window; on a live stream it is also
        # the settle latency, so keep it small. Ordering within a game is
        # already guaranteed by the strictly-increasing clock, so a short
        # window is safe and makes violations surface promptly on the page.
        self.engine = Engine(self.policies, terminal_event_types=set(),
                             grace=0.5, quiescence_ttl=3600.0)

        self._lock = threading.Lock()
        self._counter = 0
        self._cheat_seq = 0
        self.game: Minesweeper | None = None

        self.dash_url = self.dashboard.start(port=dash_port)
        self._engine_thread = threading.Thread(
            target=self.engine.run,
            kwargs={"source": self.source, "sink": self.dashboard.sink},
            daemon=True,
        )
        self._engine_thread.start()

    def _emit(self, event: Event) -> None:
        # record -> tap for the live feed -> feed the monitoring engine
        self.source.push(self.dashboard.tap(self.recorder(event)))

    def new_game(self) -> dict:
        with self._lock:
            self._counter += 1
            gid = f"game-{self._counter}"
            self.game = Minesweeper(gid, self._emit, self.clock)
            return self.game.view()

    def reveal(self, row: int, col: int) -> dict:
        with self._lock:
            if self.game is None:
                self.new_game()
            self.game.reveal(row, col)
            return self.game.view()

    def flag(self, row: int, col: int) -> dict:
        with self._lock:
            if self.game is None:
                self.new_game()
            self.game.flag(row, col)
            return self.game.view()

    def state(self) -> dict:
        with self._lock:
            if self.game is None:
                self.new_game()
            return self.game.view()

    def cheat(self, kind: str) -> dict:
        """Inject a corrupted event straight onto the stream (bypassing the
        game's guards) so the monitor is seen catching it live.

        Each cheat injects a minimal, self-contained corrupted sequence keyed
        to the current game, so it reliably demonstrates exactly its own rule
        regardless of the board's actual state. When the real game supports it
        (an actual boom, a genuinely revealed cell) the cheat piggybacks on
        that real state instead, for the most realistic demonstration. Injected
        cells use synthetic ids so they never touch the rendered board."""
        with self._lock:
            if self.game is None:
                self.new_game()
            gid = self.game.game_id
            view = self.game.view()

            if kind == "reveal_after_boom":
                if not self.game.exploded:
                    # no real boom yet: inject the explosion the illegal
                    # reveal follows, so the "game over" scope is open.
                    self._emit(Event(MINE_EXPLODED, self.clock(),
                                     {"game_id": gid}, {"cell": "injected"},
                                     SOURCE))
                self._cheat_seq += 1
                self._emit(Event(CELL_REVEAL, self.clock(),
                                 {"game_id": gid, "cell": f"ghost-{self._cheat_seq}"},
                                 {"row": -1, "col": -1, "mine": False}, SOURCE))

            elif kind == "double_reveal":
                real = self._pick(view, "revealed")
                if real is not None:
                    r, c = (int(x) for x in real.split(","))
                    self._emit(Event(CELL_REVEAL, self.clock(),
                                     {"game_id": gid, "cell": real},
                                     {"row": r, "col": c, "mine": False}, SOURCE))
                else:
                    # nothing revealed yet: inject the full first-reveal +
                    # state so the same-cell scope is armed, then the repeat.
                    self._cheat_seq += 1
                    cell = f"ghost-{self._cheat_seq}"
                    self._emit(Event(CELL_REVEAL, self.clock(),
                                     {"game_id": gid, "cell": cell},
                                     {"row": -1, "col": -1, "mine": False}, SOURCE))
                    self._emit(Event(CELL_REVEALED, self.clock(),
                                     {"game_id": gid, "cell": cell},
                                     {"row": -1, "col": -1, "adjacent": 0}, SOURCE))
                    self._emit(Event(CELL_REVEAL, self.clock(),
                                     {"game_id": gid, "cell": cell},
                                     {"row": -1, "col": -1, "mine": False}, SOURCE))

            elif kind == "over_flag":
                self._emit(Event(FLAG_PLACED, self.clock(),
                                 {"game_id": gid},
                                 {"flags": self.game.mine_count + 1,
                                  "mines": self.game.mine_count,
                                  "cell": "injected"}, SOURCE))
            else:
                return {"error": f"unknown cheat {kind!r}"}
            return {"ok": True, "kind": kind, "game_id": gid}

    @staticmethod
    def _pick(view: dict, state: str) -> str | None:
        for cell in view["cells"]:
            if cell["state"] == state:
                return f'{cell["row"]},{cell["col"]}'
        return None

    def close(self) -> None:
        self.source.close()
        self.recorder.close()
        self.dashboard.stop()


def make_handler(live: Live, dash_url: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # quiet

        def _send_json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if not length:
                return {}
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                body = PAGE.replace("__DASH_URL__", dash_url).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state":
                self._send_json(live.state())
            elif self.path == "/api/config":
                self._send_json({"dashboard": dash_url})
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            else:
                self.send_error(404)

        def do_POST(self):
            try:
                data = self._read_json()
                if self.path == "/api/new":
                    self._send_json(live.new_game())
                elif self.path == "/api/reveal":
                    self._send_json(live.reveal(int(data["row"]), int(data["col"])))
                elif self.path == "/api/flag":
                    self._send_json(live.flag(int(data["row"]), int(data["col"])))
                elif self.path == "/api/cheat":
                    self._send_json(live.cheat(str(data.get("kind", ""))))
                else:
                    self.send_error(404)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, code=400)

    return Handler


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minesweeper - live runtime verification</title>
<style>
  :root {
    --bg: #0f1220; --panel: #171b2e; --line: #2a3050; --ink: #e7ebff;
    --muted: #8b93b8; --hidden: #2b3357; --hidden2: #333c66; --rev: #10131f;
    --accent: #6ea8ff; --bad: #ff5d6c; --good: #38d39f; --flag: #ffcf5c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }
  header {
    padding: 16px 22px; border-bottom: 1px solid var(--line);
    display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;
  }
  header h1 { font-size: 18px; margin: 0; letter-spacing: .2px; }
  header .sub { color: var(--muted); font-size: 13px; }
  .wrap { display: flex; gap: 18px; padding: 18px 22px; align-items: flex-start; flex-wrap: wrap; }
  .col-game { flex: 0 0 auto; }
  .col-dash { flex: 1 1 520px; min-width: 340px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; }
  .board-card { padding: 16px; }
  .stats { display: flex; gap: 18px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }
  .stat { display: flex; flex-direction: column; }
  .stat b { font-size: 20px; font-variant-numeric: tabular-nums; }
  .stat span { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .6px; }
  .status { margin-left: auto; font-weight: 600; }
  .status.win { color: var(--good); } .status.lost { color: var(--bad); }
  .grid { display: grid; grid-template-columns: repeat(8, 40px); gap: 4px; user-select: none; }
  .cell {
    width: 40px; height: 40px; border-radius: 8px; border: none; cursor: pointer;
    font-size: 18px; font-weight: 700; display: flex; align-items: center; justify-content: center;
    background: linear-gradient(180deg, var(--hidden2), var(--hidden));
    color: var(--ink); transition: transform .05s ease;
  }
  .cell:hover { transform: translateY(-1px); }
  .cell.revealed { background: var(--rev); cursor: default; box-shadow: inset 0 0 0 1px var(--line); }
  .cell.flag { color: var(--flag); }
  .cell.mine { background: #3a1220; color: var(--bad); }
  .n1 { color:#6ea8ff } .n2 { color:#48c78e } .n3 { color:#ff7a90 }
  .n4 { color:#a78bfa } .n5 { color:#f59e0b } .n6 { color:#22d3ee }
  .n7 { color:#e879f9 } .n8 { color:#f87171 }
  .controls { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
  button.btn {
    background: #222a49; color: var(--ink); border: 1px solid var(--line);
    padding: 8px 12px; border-radius: 9px; cursor: pointer; font-size: 13px;
  }
  button.btn:hover { border-color: var(--accent); }
  .cheats { margin-top: 16px; padding: 14px; border-radius: 12px; border: 1px dashed #5a2a3a; background: #1b1420; }
  .cheats h3 { margin: 0 0 4px; font-size: 13px; color: var(--bad); letter-spacing: .3px; }
  .cheats p { margin: 0 0 10px; color: var(--muted); font-size: 12px; }
  button.cheat {
    background: #3a1622; color: #ffd7dc; border: 1px solid #6a2b3c;
    padding: 8px 12px; border-radius: 9px; cursor: pointer; font-size: 13px;
  }
  button.cheat:hover { background: #4a1c2c; }
  .dash-head { display:flex; align-items:center; gap:10px; margin-bottom: 8px; }
  .dash-head a { color: var(--accent); text-decoration: none; font-size: 13px; }
  iframe { width: 100%; height: 78vh; min-height: 520px; border: 1px solid var(--line); border-radius: 14px; background:#fff; }
  .hint { color: var(--muted); font-size: 12px; margin-top: 8px; }
  .toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
    background: #3a1622; color: #ffd7dc; border: 1px solid #6a2b3c; padding: 10px 16px;
    border-radius: 10px; opacity: 0; transition: opacity .2s; pointer-events: none; }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
<header>
  <h1>Minesweeper</h1>
  <span class="sub">8&times;8 &middot; 10 mines &middot; left-click reveal, right-click flag &middot; verified live by behave-rv</span>
</header>
<div class="wrap">
  <div class="col-game">
    <div class="card board-card">
      <div class="stats">
        <div class="stat"><b id="mines">10</b><span>mines</span></div>
        <div class="stat"><b id="flags">0</b><span>flags</span></div>
        <div class="stat status" id="status">playing</div>
      </div>
      <div class="grid" id="grid"></div>
      <div class="controls">
        <button class="btn" onclick="newGame()">New game</button>
      </div>
      <div class="cheats">
        <h3>Inject a corrupted event (bypasses the game)</h3>
        <p>These push a raw event onto the monitor's stream, dodging every
           in-game guard - watch the matching policy card turn red.</p>
        <button class="cheat" onclick="cheat('reveal_after_boom')">Reveal after boom</button>
        <button class="cheat" onclick="cheat('double_reveal')">Double-reveal a cell</button>
        <button class="cheat" onclick="cheat('over_flag')">Plant an 11th flag</button>
        <div class="hint">Each button injects a self-contained corrupted sequence, so it works any time - but if you lose a game first (click a mine) then hit "reveal after boom", the illegal reveal follows your real explosion. Verdicts settle within ~1s.</div>
      </div>
    </div>
  </div>
  <div class="col-dash">
    <div class="dash-head">
      <strong>Live monitor</strong>
      <a href="__DASH_URL__" target="_blank" rel="noopener">open in a new tab &#8599;</a>
    </div>
    <iframe src="__DASH_URL__" title="behave-rv dashboard"></iframe>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
const NUM_COLORS = ["","n1","n2","n3","n4","n5","n6","n7","n8"];
let over = false;

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1800);
}

function render(view) {
  over = view.over;
  document.getElementById('mines').textContent = view.mines;
  document.getElementById('flags').textContent = view.flags;
  const s = document.getElementById('status');
  if (view.won) { s.textContent = 'you win'; s.className = 'status win'; }
  else if (view.exploded) { s.textContent = 'boom - game over'; s.className = 'status lost'; }
  else { s.textContent = 'playing'; s.className = 'status'; }

  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  for (const c of view.cells) {
    const el = document.createElement('button');
    el.className = 'cell';
    if (c.state === 'revealed') {
      el.classList.add('revealed');
      if (c.mine) { el.classList.add('mine'); el.textContent = '\u{1F4A3}'; }
      else if (c.adjacent > 0) { el.classList.add(NUM_COLORS[c.adjacent]); el.textContent = c.adjacent; }
    } else if (c.state === 'flagged') {
      el.classList.add('flag'); el.textContent = '\u{1F6A9}';
    } else if (c.mine) {
      el.classList.add('mine'); el.textContent = '\u{1F4A3}';
    }
    el.oncontextmenu = (ev) => { ev.preventDefault(); flag(c.row, c.col); };
    el.onclick = () => reveal(c.row, c.col);
    grid.appendChild(el);
  }
}

async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: {'Content-Type':'application/json'},
                                body: JSON.stringify(body || {}) });
  return r.json();
}
async function reveal(row, col) { if (!over) render(await post('/api/reveal', {row, col})); }
async function flag(row, col) { if (!over) render(await post('/api/flag', {row, col})); }
async function newGame() { render(await post('/api/new', {})); }
async function cheat(kind) {
  const res = await post('/api/cheat', {kind});
  if (res.error) toast(res.error);
  else toast('injected: ' + kind + ' - check the monitor');
}
async function init() {
  const r = await fetch('/api/state'); render(await r.json());
}
init();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Browser Minesweeper + behave-rv monitor")
    ap.add_argument("--game-port", type=int, default=8803)
    ap.add_argument("--dash-port", type=int, default=7103)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    live = Live(args.dash_port)
    live.new_game()
    handler = make_handler(live, live.dash_url)
    httpd = ThreadingHTTPServer((args.host, args.game_port), handler)
    game_url = f"http://{args.host}:{args.game_port}"

    print(f"game:  {game_url}")
    print(f"live monitor: {live.dash_url}")
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        httpd.shutdown()
        live.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
