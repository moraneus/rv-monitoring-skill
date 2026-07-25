"""The live Snake app: a browser front-end over the Python game engine, with a
behave-rv monitor and its dashboard running alongside.

Architecture (stdlib only):
* The authoritative game logic runs here in Python (``SnakeGame``); the browser
  is a thin client - it renders ``/state`` on a canvas and sends arrow keys to
  ``/input``.
* Every state transition the engine emits flows to the monitor: the emit chain
  is ``source.push(dashboard.tap(recorder(event)))`` - the dashboard sees it in
  its live feed, the recorder tees it to a replayable trace, and the engine
  (running in its own thread) delivers verdicts to ``dashboard.sink``.
* A service-relative clock (``time.time() - start``) keeps event times small and
  readable and lets wall-fired ``within`` deadlines resolve on a quiet stream.

Ports (both configurable): game UI on 8801, dashboard on 7101.

    python -m app.server [--game-port 8801] [--dash-port 7101]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.game import (EVT_FOOD, EVT_GROW, EVT_MOVE, EVT_STATUS,  # noqa: E402
                      SnakeGame)
from steps import build_registry, load_policies                 # noqa: E402

TICK_MS = 140
GRID_W = 20
GRID_H = 20


class GameManager:
    """Owns the current game, its tick loop, and browser input. All game state
    changes happen under one lock so the tick thread and HTTP threads agree."""

    def __init__(self, emit, clock):
        self._emit = emit
        self._clock = clock
        self._lock = threading.Lock()
        self._seq = 0
        self._game: SnakeGame | None = None
        self._corrupt_seq = 0
        self.new_game()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def new_game(self) -> None:
        with self._lock:
            self._seq += 1
            gid = f"live-{self._seq}"
            self._game = SnakeGame(gid, self._emit, self._clock,
                                   width=GRID_W, height=GRID_H)
            self._game.start()

    def input(self, direction: str) -> None:
        with self._lock:
            if self._game is not None:
                self._game.set_direction(direction)

    def snapshot(self) -> dict:
        with self._lock:
            return self._game.snapshot() if self._game else {}

    def _run(self) -> None:
        while not self._stop.is_set():
            time.sleep(TICK_MS / 1000.0)
            with self._lock:
                if self._game is not None and not self._game.over:
                    self._game.tick()

    def stop(self) -> None:
        self._stop.set()

    def inject_corruption(self, rule: str) -> str:
        """Emit a self-contained corrupted sequence under a fresh game id, so a
        violation always appears on the dashboard without touching live play.
        Returns the synthetic game id."""
        self._corrupt_seq += 1
        gid = f"corrupt-{rule}-{self._corrupt_seq}"
        t0 = self._clock()

        def raw(dt: float, type: str, payload: dict) -> None:
            self._emit(Event(type, t0 + dt, {"game_id": gid}, payload,
                             "corrupted"))

        if rule == "1move":            # a move after game over
            raw(0.00, EVT_STATUS, {"status": "started", "score": 0, "length": 3})
            raw(0.02, EVT_STATUS, {"status": "over", "reason": "wall",
                                   "score": 0, "length": 3})
            raw(0.04, EVT_MOVE, {"direction": "up", "prev_direction": "up"})
        elif rule == "1point":         # a point after game over
            raw(0.00, EVT_STATUS, {"status": "started", "score": 0, "length": 3})
            raw(0.02, EVT_STATUS, {"status": "over", "reason": "wall",
                                   "score": 7, "length": 5})
            raw(0.04, EVT_FOOD, {"score": 8})
        elif rule == "2":              # food eaten, snake never grows in 2s
            raw(0.00, EVT_STATUS, {"status": "started", "score": 0, "length": 3})
            raw(0.02, EVT_FOOD, {"score": 1})
        elif rule == "3":              # a 180-degree reversal is accepted
            raw(0.00, EVT_STATUS, {"status": "started", "score": 0, "length": 3})
            raw(0.02, EVT_MOVE, {"direction": "right", "prev_direction": "right"})
            raw(0.04, EVT_MOVE, {"direction": "left", "prev_direction": "right"})
        return gid


def _page(dash_url: str) -> bytes:
    return PAGE_HTML.replace("__DASH_URL__", dash_url).encode("utf-8")


def make_handler(manager: GameManager, dash_url: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):        # keep the console clean
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, _page(dash_url), "text/html; charset=utf-8")
            elif path == "/state":
                snap = manager.snapshot()
                snap["dashboard"] = dash_url
                self._send(200, json.dumps(snap).encode())
            else:
                self._send(404, b"{}")

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode() if length else ""
            params = parse_qs(raw)
            qs = parse_qs(parsed.query)
            if path == "/input":
                direction = (params.get("dir") or qs.get("dir") or [""])[0]
                manager.input(direction)
                self._send(200, b"{}")
            elif path == "/new":
                manager.new_game()
                self._send(200, b"{}")
            elif path == "/corrupt":
                rule = (params.get("rule") or qs.get("rule") or [""])[0]
                gid = manager.inject_corruption(rule)
                self._send(200, json.dumps({"injected": gid}).encode())
            else:
                self._send(404, b"{}")

    return Handler


PAGE_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Snake - runtime verified</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, sans-serif; background: #0b1020;
         color: #e6ebff; display: flex; justify-content: center; }
  .wrap { width: min(560px, 94vw); padding: 24px 16px 48px; }
  h1 { font-size: 20px; margin: 0 0 2px; letter-spacing: .3px; }
  .sub { color: #8b97c4; margin: 0 0 18px; font-size: 13px; }
  .hud { display: flex; gap: 10px; margin-bottom: 12px; }
  .chip { background: #161d38; border: 1px solid #26305a; border-radius: 10px;
          padding: 8px 12px; flex: 1; text-align: center; }
  .chip b { display: block; font-size: 20px; }
  .chip span { color: #8b97c4; font-size: 11px; text-transform: uppercase;
               letter-spacing: .5px; }
  canvas { width: 100%; aspect-ratio: 1; background: #0f1530; border-radius: 14px;
           border: 1px solid #26305a; touch-action: none; display: block; }
  .over { color: #ff8a8a; font-weight: 600; height: 20px; margin: 10px 2px;
          text-align: center; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
  button { background: #1c2547; color: #e6ebff;
           border: 1px solid #2f3b6e; border-radius: 9px; padding: 9px 12px;
           font-size: 13px; cursor: pointer; }
  button:hover { background: #263166; }
  button.primary { background: #3552d6; border-color: #3552d6; }
  .panel { margin-top: 20px; background: #10162e; border: 1px solid #26305a;
           border-radius: 12px; padding: 14px 16px; }
  .panel h2 { font-size: 13px; margin: 0 0 6px; color: #b9c3ee;
              text-transform: uppercase; letter-spacing: .6px; }
  .panel p { margin: 0 0 12px; color: #8b97c4; font-size: 12px; }
  .rules { margin: 0; padding-left: 18px; color: #aeb8e2; font-size: 12px; }
  .rules li { margin: 3px 0; }
  a { color: #8ea2ff; }
  .link { display: inline-block; margin-top: 6px; font-size: 13px; }
</style></head>
<body><div class="wrap">
  <h1>Snake <span style="color:#8ea2ff">// runtime verified</span></h1>
  <p class="sub">Arrow keys or WASD to steer. A behave-rv monitor watches every
     move on the <a href="__DASH_URL__" target="_blank">live dashboard</a>.</p>

  <div class="hud">
    <div class="chip"><b id="score">0</b><span>score</span></div>
    <div class="chip"><b id="length">3</b><span>length</span></div>
    <div class="chip"><b id="status">live</b><span>game</span></div>
  </div>

  <canvas id="board" width="400" height="400"></canvas>
  <div class="over" id="msg"></div>

  <div class="row">
    <button class="primary" onclick="newGame()">New game</button>
    <a class="link" href="__DASH_URL__" target="_blank">Open monitor dashboard &rarr;</a>
  </div>

  <div class="panel">
    <h2>Monitored rules</h2>
    <ul class="rules">
      <li>Once a game is over, no further moves or points may ever be scored.</li>
      <li>Every food eaten must be followed by growth within 2 seconds.</li>
      <li>The snake must never reverse straight into itself (a 180&deg; turn).</li>
    </ul>
  </div>

  <div class="panel">
    <h2>See a violation live</h2>
    <p>Honest play never breaks a rule (that is the point). These buttons inject
       a corrupted event into a throwaway game so you can watch the matching
       policy card turn red on the dashboard.</p>
    <div class="row">
      <button onclick="corrupt('1move')">Move after over</button>
      <button onclick="corrupt('1point')">Point after over</button>
      <button onclick="corrupt('2')">Food, no growth</button>
      <button onclick="corrupt('3')">180&deg; reversal</button>
    </div>
  </div>
</div>
<script>
const cv = document.getElementById('board'), cx = cv.getContext('2d');
let W = 20, H = 20;
const DIRS = {ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right',
              w:'up', s:'down', a:'left', d:'right'};

async function post(url) { try { await fetch(url, {method:'POST'}); } catch(e){} }
function newGame() { post('/new'); }
function corrupt(rule) { post('/corrupt?rule=' + rule); }

document.addEventListener('keydown', e => {
  const d = DIRS[e.key];
  if (d) { e.preventDefault(); post('/input?dir=' + d); }
});

function draw(s) {
  W = s.w; H = s.h;
  const px = cv.width / W;
  cx.fillStyle = '#0f1530'; cx.fillRect(0, 0, cv.width, cv.height);
  cx.strokeStyle = '#182046';
  for (let i = 1; i < W; i++) {
    cx.beginPath(); cx.moveTo(i*px, 0); cx.lineTo(i*px, cv.height); cx.stroke();
    cx.beginPath(); cx.moveTo(0, i*px); cx.lineTo(cv.width, i*px); cx.stroke();
  }
  if (s.food) {
    cx.fillStyle = '#ff5d73';
    cx.beginPath();
    cx.arc((s.food[0]+.5)*px, (s.food[1]+.5)*px, px*0.32, 0, 7); cx.fill();
  }
  (s.snake || []).forEach((c, i) => {
    cx.fillStyle = i === 0 ? '#7ce7a6' : '#3fae74';
    const pad = 1.2;
    cx.fillRect(c[0]*px+pad, c[1]*px+pad, px-2*pad, px-2*pad);
  });
}

async function loop() {
  try {
    const s = await (await fetch('/state')).json();
    if (s.snake) {
      draw(s);
      document.getElementById('score').textContent = s.score;
      document.getElementById('length').textContent = s.length;
      document.getElementById('status').textContent = s.over ? 'over' : 'live';
      document.getElementById('msg').textContent =
        s.over ? ('Game over - ' + s.reason + '. Press New game.') : '';
    }
  } catch (e) {}
  setTimeout(loop, 90);
}
loop();
</script>
</body></html>"""


def build_monitor(dash_port: int):
    registry = build_registry()
    policies = load_policies(registry)
    start = time.time()
    clock = lambda: time.time() - start

    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "game.py"),
                               str(ROOT / "app" / "traffic.py")])
    trace_path = ROOT / "monitoring" / "traces" / "live_session.jsonl"
    recorder = TraceRecorder(str(trace_path), clock=clock)

    def emit(event: Event) -> None:
        source.push(dashboard.tap(recorder(event)))

    # No terminal event: "over" must not settle the entity, or the post-over
    # prohibitions would flip to a false green the instant the game ends. A
    # small grace keeps the live verdict delivery snappy on a fast UI stream.
    engine = Engine(policies, terminal_event_types=set(), grace=0.25)
    dash_url = dashboard.start(port=dash_port)

    engine_thread = threading.Thread(
        target=lambda: engine.run(source, sink=dashboard.sink), daemon=True)
    engine_thread.start()
    return emit, clock, dashboard, source, recorder, dash_url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-port", type=int, default=8801)
    ap.add_argument("--dash-port", type=int, default=7101)
    args = ap.parse_args()

    emit, clock, dashboard, source, recorder, dash_url = build_monitor(args.dash_port)
    manager = GameManager(emit, clock)

    handler = make_handler(manager, dash_url)
    server = ThreadingHTTPServer(("127.0.0.1", args.game_port), handler)
    game_url = f"http://127.0.0.1:{args.game_port}"

    print(f"Snake game:     {game_url}", flush=True)
    print(f"live monitor:   {dash_url}", flush=True)
    print("Ctrl-C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()
        server.shutdown()
        source.close()
        recorder.close()
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
