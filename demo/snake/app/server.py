"""Browser front end for the Snake game - stdlib http.server only.

The authoritative game runs here, on the server: the browser sends arrow-key
input and polls board state, while the server ticks each game and the
``SnakeService`` emits its events to the monitor. This keeps the monitored
surface where it belongs (the application), not in the client.

No ``Event`` is constructed in this file - all instrumentation lives in
``game.py``, so the stability ``--app`` slice is exactly ``app/game.py``.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.game import SnakeService

DEFAULT_TICK_MS = 130


class SnakeServer:
    def __init__(self, service: SnakeService, lock: threading.Lock,
                 host: str = "127.0.0.1", port: int = 8801,
                 tick_ms: int = DEFAULT_TICK_MS, dashboard_url: str = ""):
        self.service = service
        self.lock = lock
        self.host = host
        self.port = port
        self.tick_ms = tick_ms
        self.dashboard_url = dashboard_url
        self._counter = 0
        self._httpd: ThreadingHTTPServer | None = None
        self._stop = threading.Event()

    # --- game control (all under the shared lock) -----------------------------
    def new_game(self) -> dict:
        with self.lock:
            self._counter += 1
            game_id = f"web-{self._counter}"
            state = self.service.new_game(game_id, seed=int(time.time() * 1000) & 0xFFFF)
            return state.snapshot()

    def input(self, game_id: str, direction: str) -> str:
        with self.lock:
            return self.service.set_direction(game_id, direction)

    def state(self, game_id: str) -> dict | None:
        with self.lock:
            return self.service.snapshot(game_id)

    def _tick_loop(self) -> None:
        dt = self.tick_ms / 1000.0
        while not self._stop.is_set():
            with self.lock:
                for gid, gs in list(self.service.games.items()):
                    if gs.alive:
                        self.service.tick(gid)
            time.sleep(dt)

    # --- lifecycle ------------------------------------------------------------
    def start(self) -> str:
        handler = _make_handler(self)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._tick_loop, daemon=True).start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        self._stop.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()


def _make_handler(server: SnakeServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):     # keep the console clean
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif parsed.path == "/api/config":
                self._json({"tick_ms": server.tick_ms,
                            "dashboard_url": server.dashboard_url})
            elif parsed.path == "/api/state":
                gid = parse_qs(parsed.query).get("game_id", [""])[0]
                st = server.state(gid)
                self._json(st if st else {"error": "unknown game"},
                           200 if st else 404)
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            parsed = urlparse(self.path)
            q = parse_qs(parsed.query)
            if parsed.path == "/api/new":
                self._json(server.new_game())
            elif parsed.path == "/api/input":
                gid = q.get("game_id", [""])[0]
                direction = q.get("dir", [""])[0]
                self._json({"result": server.input(gid, direction)})
            else:
                self._json({"error": "not found"}, 404)

    return Handler


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Snake - runtime verified</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 18px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: radial-gradient(1200px 800px at 50% -10%, #14342b, #06110d 60%);
    color: #d7f5e6;
  }
  h1 { margin: 8px 0 0; font-size: 20px; letter-spacing: 2px; font-weight: 700;
       color: #8ef0bd; text-shadow: 0 0 18px rgba(90,240,180,.35); }
  .hud { display: flex; gap: 26px; align-items: baseline; font-size: 15px; }
  .hud b { color: #8ef0bd; font-size: 22px; }
  .stage { position: relative; }
  canvas { background: #071912; border: 1px solid #1f4d3c;
           border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,.5); }
  .overlay {
    position: absolute; inset: 0; display: none; flex-direction: column;
    align-items: center; justify-content: center; gap: 14px;
    background: rgba(4,14,10,.82); border-radius: 10px; text-align: center;
  }
  .overlay.show { display: flex; }
  .overlay .big { font-size: 26px; color: #ff8a8a; letter-spacing: 1px; }
  button {
    font-family: inherit; font-size: 15px; padding: 10px 20px; cursor: pointer;
    color: #06110d; background: #6ee7a8; border: 0; border-radius: 8px;
    font-weight: 700; letter-spacing: 1px;
  }
  button:hover { background: #8ef0bd; }
  .foot { font-size: 12px; color: #6fae92; text-align: center; line-height: 1.7; }
  .foot a { color: #8ef0bd; }
  kbd { background: #10281f; border: 1px solid #26543f; border-radius: 4px;
        padding: 1px 6px; color: #b9f2d5; }
</style>
</head>
<body>
  <h1>S N A K E</h1>
  <div class="hud">
    <div>score <b id="score">0</b></div>
    <div>length <b id="length">3</b></div>
  </div>
  <div class="stage">
    <canvas id="board" width="480" height="480"></canvas>
    <div class="overlay" id="overlay">
      <div class="big" id="reason">GAME OVER</div>
      <button id="again">PLAY AGAIN</button>
    </div>
  </div>
  <div class="foot">
    <div>Move with the <kbd>arrow keys</kbd>. A 180-degree turn is refused.</div>
    <div id="monitorline"></div>
  </div>
<script>
const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');
const scoreEl = document.getElementById('score');
const lengthEl = document.getElementById('length');
const overlay = document.getElementById('overlay');
const reasonEl = document.getElementById('reason');
let gameId = null, tickMs = 130, cell = 20, gridW = 24, gridH = 24, polling = null;

async function boot() {
  const cfg = await (await fetch('/api/config')).json();
  tickMs = cfg.tick_ms;
  if (cfg.dashboard_url) {
    document.getElementById('monitorline').innerHTML =
      'Live behave-rv monitor: <a href="' + cfg.dashboard_url +
      '" target="_blank">' + cfg.dashboard_url + '</a>';
  }
  await newGame();
}

async function newGame() {
  const st = await (await fetch('/api/new', {method:'POST'})).json();
  gameId = st.game_id; gridW = st.grid_w; gridH = st.grid_h;
  cell = Math.floor(canvas.width / gridW);
  overlay.classList.remove('show');
  if (polling) clearInterval(polling);
  polling = setInterval(refresh, tickMs);
  draw(st);
}

async function refresh() {
  if (!gameId) return;
  const st = await (await fetch('/api/state?game_id=' + gameId)).json();
  if (st.error) return;
  draw(st);
  if (!st.alive) {
    clearInterval(polling); polling = null;
    reasonEl.textContent = st.reason === 'self'
      ? 'YOU BIT YOURSELF' : 'YOU HIT THE WALL';
    overlay.classList.add('show');
  }
}

function draw(st) {
  scoreEl.textContent = st.score;
  lengthEl.textContent = st.length;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  // subtle grid
  ctx.strokeStyle = 'rgba(40,90,70,.25)';
  for (let i = 0; i <= gridW; i++) {
    ctx.beginPath(); ctx.moveTo(i*cell, 0); ctx.lineTo(i*cell, gridH*cell); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i*cell); ctx.lineTo(gridW*cell, i*cell); ctx.stroke();
  }
  // food
  const [fx, fy] = st.food;
  ctx.fillStyle = '#ff6b6b';
  ctx.beginPath();
  ctx.arc(fx*cell + cell/2, fy*cell + cell/2, cell*0.36, 0, Math.PI*2);
  ctx.fill();
  // snake
  st.snake.forEach(([x, y], i) => {
    ctx.fillStyle = i === 0 ? '#8ef0bd' : '#3fae7a';
    const p = 2;
    ctx.fillRect(x*cell + p, y*cell + p, cell - 2*p, cell - 2*p);
  });
}

const KEYMAP = {ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right'};
document.addEventListener('keydown', (e) => {
  const dir = KEYMAP[e.key];
  if (!dir || !gameId) return;
  e.preventDefault();
  fetch('/api/input?game_id=' + gameId + '&dir=' + dir, {method:'POST'});
});
document.getElementById('again').addEventListener('click', newGame);
boot();
</script>
</body>
</html>
"""
