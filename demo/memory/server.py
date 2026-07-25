"""Browser Memory game + live behave-rv dashboard.

    python server.py            # game at :8805, monitor at :7105

The game page (stdlib http.server, all HTML/JS inline, no CDNs) drives the
real, honest MemoryGame service on the server side; every state change emits
an Event that is tapped into a live engine and rendered on the behave-rv
dashboard. Open BOTH URLs printed at startup: play on one, watch your three
rules hold on the other. Healthy play never violates - the cheats live in
demo.py.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder       # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.game import MemoryGame, FLIPBACK_DELAY, deal           # noqa: E402
from steps import build_registry, load_policies                # noqa: E402

EMOJI = {"fox": "🦊", "owl": "🦉", "bee": "🐝", "cat": "🐱",
         "koi": "🐟", "elk": "🦌", "ram": "🐏", "jay": "🐦"}

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Memory · monitored</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{--bg:#0f1220;--card:#1b2036;--up:#2a3355;--match:#1f7a4d;--line:#2c3350;
        --ink:#e8ecff;--dim:#8b93b8;--acc:#6c7bff}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       display:flex;flex-direction:column;align-items:center;min-height:100vh}
  header{text-align:center;margin:28px 16px 8px}
  h1{margin:0;font-size:22px;letter-spacing:.3px}
  .sub{color:var(--dim);font-size:13px;margin-top:4px}
  .sub a{color:var(--acc);text-decoration:none}
  #board{display:grid;grid-template-columns:repeat(4,84px);gap:12px;margin:22px}
  .card{width:84px;height:104px;border:none;border-radius:14px;background:var(--card);
        font-size:40px;cursor:pointer;color:var(--ink);position:relative;
        transition:transform .15s,background .2s;box-shadow:0 4px 14px #0006}
  .card:hover:not(:disabled){transform:translateY(-3px)}
  .card:disabled{cursor:default}
  .card.up{background:var(--up)}
  .card.match{background:var(--match);box-shadow:0 0 0 2px #34d39955}
  .card .back{color:#3a4370;font-size:26px}
  #status{min-height:24px;font-size:14px;color:var(--dim);margin:4px}
  #status b{color:var(--ink)}
  .bar{display:flex;gap:10px;align-items:center;margin:8px}
  button.act{background:var(--acc);color:#fff;border:none;border-radius:9px;
             padding:9px 16px;font-size:14px;cursor:pointer}
  .win{color:#34d399;font-weight:600}
</style></head>
<body>
  <header>
    <h1>🃏 Memory — runtime-verified</h1>
    <div class="sub">Live monitor (your three rules): <a id="mon" href="#" target="_blank">opening…</a></div>
  </header>
  <div id="board"></div>
  <div id="status">Loading…</div>
  <div class="bar"><button class="act" onclick="newGame()">New game</button></div>
<script>
let GID=null, MON="__MON__";
document.getElementById('mon').href=MON; document.getElementById('mon').textContent=MON;
const board=document.getElementById('board'), status=document.getElementById('status');
const EMOJI=__EMOJI__;
function render(v){
  GID=v.game_id; board.innerHTML='';
  v.cards.forEach(c=>{
    const b=document.createElement('button'); b.className='card';
    if(c.matched) b.className+=' match'; else if(c.face_up) b.className+=' up';
    if(c.symbol){ b.textContent=EMOJI[c.symbol]||c.symbol; }
    else { const s=document.createElement('span'); s.className='back'; s.textContent='?'; b.appendChild(s); }
    b.disabled = c.matched || c.face_up || v.busy && !c.face_up || v.completed;
    b.onclick=()=>flip(c.position);
    board.appendChild(b);
  });
  if(v.completed){ status.innerHTML='<span class="win">🎉 Complete — all '+v.pairs+' pairs found. The game is now sealed.</span>'; }
  else { status.innerHTML='Pairs found: <b>'+v.matched_pairs+' / '+v.pairs+'</b>'+(v.busy?' · resolving…':''); }
  if(v.busy && !v.completed) setTimeout(()=>poll(), 260);
}
async function newGame(){ const r=await fetch('/api/new',{method:'POST'}); render(await r.json()); }
async function flip(pos){ const r=await fetch('/api/flip',{method:'POST',
  headers:{'Content-Type':'application/json'}, body:JSON.stringify({game_id:GID,position:pos})}); render(await r.json()); }
async function poll(){ const r=await fetch('/api/state?game_id='+encodeURIComponent(GID)); render(await r.json()); }
newGame();
</script>
</body></html>"""


class GameHub:
    """Server-side home of the honest games and the live monitor wiring."""

    def __init__(self, monitor_url_holder):
        self.lock = threading.Lock()
        self.games: dict[str, MemoryGame] = {}
        self.counter = 0
        self.start = time.time()
        self.clock = lambda: time.time() - self.start

        registry = build_registry()
        policies = load_policies(registry)
        self.dashboard = Dashboard(policies, registry=registry,
                                   catalog="monitoring/catalog.json",
                                   app=["app/game.py"])
        self.recorder = TraceRecorder("monitoring/traces/live_session.jsonl",
                                      clock=self.clock)
        self.source = QueueSource()
        self._emit = lambda e: self.source.push(self.dashboard.tap(self.recorder(e)))
        self.engine = Engine(policies, terminal_event_types={"game.completed"},
                             grace=0.4)
        threading.Thread(target=lambda: self.engine.run(self.source,
                         sink=self.dashboard.sink), daemon=True).start()

    def new_game(self) -> dict:
        with self.lock:
            self.counter += 1
            gid = f"web-{self.counter}"
            game = MemoryGame(gid, self._emit, self.clock, deal())
            self.games[gid] = game
            game.start()
            return game.view()

    def flip(self, gid: str, pos: int) -> dict:
        with self.lock:
            game = self.games.get(gid)
            if game is None:
                return {"error": "no such game"}
            legal = (not game.completed and not game.awaiting
                     and pos not in game.matched and pos not in game.face_up)
            if legal:
                game.flip(pos)
                if game.awaiting:                     # mismatch: schedule flip-back
                    threading.Timer(FLIPBACK_DELAY, self._flip_back, (gid,)).start()
            return game.view()

    def _flip_back(self, gid: str) -> None:
        with self.lock:
            game = self.games.get(gid)
            if game is not None:
                game.resolve_mismatch()

    def state(self, gid: str) -> dict:
        with self.lock:
            game = self.games.get(gid)
            return game.view() if game else {"error": "no such game"}


def make_handler(hub: GameHub, page: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):      # keep the console quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj):
            self._send(200, json.dumps(obj))

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                self._send(200, page, "text/html; charset=utf-8")
            elif u.path == "/api/state":
                gid = parse_qs(u.query).get("game_id", [""])[0]
                self._json(hub.state(gid))
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/api/new":
                self._json(hub.new_game())
            elif u.path == "/api/flip":
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or "{}")
                self._json(hub.flip(body["game_id"], int(body["position"])))
            else:
                self._send(404, "not found", "text/plain")
    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-port", type=int, default=8805)
    ap.add_argument("--monitor-port", type=int, default=7105)
    args = ap.parse_args()

    hub = GameHub(None)
    monitor_url = hub.dashboard.start(port=args.monitor_port)
    page = (PAGE.replace("__MON__", monitor_url)
                .replace("__EMOJI__", json.dumps(EMOJI)))
    httpd = ThreadingHTTPServer(("127.0.0.1", args.game_port),
                                make_handler(hub, page))
    print(f"game:          http://127.0.0.1:{args.game_port}")
    print(f"live monitor:  {monitor_url}")
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        hub.recorder.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
