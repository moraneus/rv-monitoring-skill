"""Browser tic-tac-toe with runtime verification built in.

Serves a two-players-at-one-keyboard game (click the squares, X and O alternate)
on one port, and runs the behave-rv dashboard alongside on another. Every move
and lifecycle change is emitted to the monitor as it happens, so the dashboard
shows the three laws holding live in your own policy wording. A small "inject a
corrupted event" panel lets you fire the two illegal events on demand and watch
the matching policy go red.

    python server.py                       # game on :8804, dashboard on :7104
    python server.py --port 8804 --dashboard-port 7104

Standard library only (plus behave-rv). All HTML/CSS/JS is inline; no CDNs.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                         # noqa: E402
from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.subscription import QueueSource     # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder         # noqa: E402

from app.game_service import TicTacToeService, ENDED_TYPE         # noqa: E402
from steps import build_registry, load_policies                  # noqa: E402

CATALOG_PATH = ROOT / "monitoring" / "catalog.json"
APP_PATH = ROOT / "app" / "game_service.py"
TRACE_PATH = ROOT / "monitoring" / "traces" / "live_session.jsonl"


class Table:
    """A single game table: the shared service, a running game_id counter, and a
    manually-advanced game_id lifecycle. Guarded by a lock because HTTP requests
    arrive on many threads."""

    def __init__(self, service: TicTacToeService, dashboard_url: str) -> None:
        self._service = service
        self._lock = threading.Lock()
        self._counter = 0
        self._game_id = ""
        self.dashboard_url = dashboard_url
        self._new_game_locked()

    def _new_game_locked(self) -> None:
        self._counter += 1
        self._game_id = f"g{self._counter}"
        self._service.new_game(self._game_id)

    def state(self) -> dict:
        with self._lock:
            snap = self._service.snapshot(self._game_id) or {}
            return {"game_id": self._game_id, **snap}

    def move(self, cell: int) -> dict:
        with self._lock:
            self._service.play(self._game_id, cell)
            return {"game_id": self._game_id,
                    **(self._service.snapshot(self._game_id) or {})}

    def new_game(self) -> dict:
        with self._lock:
            # retire the current game (settles its monitors) before the next
            self._service.end_game(self._game_id)
            self._new_game_locked()
            return {"game_id": self._game_id,
                    **(self._service.snapshot(self._game_id) or {})}

    def inject(self, kind: str) -> dict:
        """Fire a corrupted move for the demo. 'double' = the last player moves
        again (no alternation); 'after_win' = a move after the game is finished;
        'orphan' = a move for a game_id that never started."""
        with self._lock:
            gid = self._game_id
            if kind == "orphan":
                # a move for a game that was never started -- stream corruption
                self._counter += 1
                phantom = f"g{self._counter}-orphan"
                self._service.force_move(phantom, "X", 0)
                return {"game_id": gid,
                        **(self._service.snapshot(gid) or {})}
            snap = self._service.snapshot(gid) or {}
            board = snap.get("board", [None] * 9)
            empties = [i for i, c in enumerate(board) if c is None]
            if kind == "double":
                # ensure there is a prior move to repeat
                if snap.get("last_mover") is None:
                    if empties:
                        self._service.play(gid, empties[0])
                        snap = self._service.snapshot(gid) or {}
                        board = snap.get("board", board)
                        empties = [i for i, c in enumerate(board) if c is None]
                player = snap.get("last_mover") or "X"
                cell = empties[0] if empties else 0
                self._service.force_move(gid, player, cell)
            elif kind == "after_win":
                if not snap.get("over"):
                    return {"game_id": gid, "error": "finish the game first",
                            **snap}
                player = "O" if snap.get("winner") == "X" else "X"
                cell = empties[0] if empties else 0
                self._service.force_move(gid, player, cell)
            return {"game_id": gid, **(self._service.snapshot(gid) or {})}


def make_handler(table: Table):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return {}

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                html = PAGE.replace("__DASHBOARD_URL__", table.dashboard_url)
                self._send(200, html.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._json(table.state())
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path == "/api/move":
                cell = int(self._body().get("cell", -1))
                self._json(table.move(cell))
            elif self.path == "/api/new":
                self._json(table.new_game())
            elif self.path == "/api/inject":
                kind = str(self._body().get("kind", ""))
                self._json(table.inject(kind))
            else:
                self._send(404, b"not found", "text/plain")

    return Handler


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tic-Tac-Toe - verified live</title>
<style>
  :root {
    --bg:#0f1220; --panel:#181c2e; --line:#2a3050; --ink:#e8ebf7;
    --muted:#9aa3c7; --x:#5cc8ff; --o:#ff7ba6; --ok:#39d98a; --bad:#ff5470;
    --accent:#8b7bff;
  }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    background:radial-gradient(1200px 600px at 70% -10%,#1b2140,transparent),var(--bg);
    color:var(--ink); min-height:100vh; }
  .wrap { max-width:900px; margin:0 auto; padding:28px 20px 60px; }
  h1 { font-size:24px; margin:0 0 4px; letter-spacing:.2px; }
  .sub { color:var(--muted); margin:0 0 24px; }
  .grid { display:grid; grid-template-columns:1fr 320px; gap:24px; align-items:start; }
  @media (max-width:760px){ .grid{ grid-template-columns:1fr; } }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:16px;
    padding:20px; }
  .status { display:flex; align-items:center; gap:10px; margin-bottom:16px; font-weight:600; }
  .dot { width:12px; height:12px; border-radius:50%; background:var(--muted); }
  .dot.x { background:var(--x); } .dot.o { background:var(--o); }
  .board { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  .cell { aspect-ratio:1/1; border:none; border-radius:14px; background:#11152a;
    box-shadow:inset 0 0 0 1px var(--line); font-size:44px; font-weight:800; cursor:pointer;
    color:var(--ink); transition:transform .05s, box-shadow .15s, background .15s; }
  .cell:hover:not(:disabled){ background:#161b36; box-shadow:inset 0 0 0 1px var(--accent); }
  .cell:active:not(:disabled){ transform:scale(.97); }
  .cell:disabled{ cursor:default; }
  .cell.x { color:var(--x); } .cell.o { color:var(--o); }
  .row { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
  button.act { background:var(--accent); color:#fff; border:none; padding:10px 16px;
    border-radius:10px; font-weight:600; cursor:pointer; }
  button.act.ghost { background:transparent; color:var(--ink); box-shadow:inset 0 0 0 1px var(--line); }
  button.danger { background:transparent; color:var(--bad); box-shadow:inset 0 0 0 1px var(--bad);
    border:none; padding:9px 12px; border-radius:10px; font-weight:600; cursor:pointer; font-size:13px; }
  button:disabled{ opacity:.4; cursor:default; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.12em; color:var(--muted);
    margin:0 0 12px; }
  .law { padding:10px 12px; border-radius:10px; background:#11152a; margin-bottom:10px;
    box-shadow:inset 0 0 0 1px var(--line); }
  .law b { display:block; font-size:13px; }
  .law span { color:var(--muted); font-size:12.5px; }
  .banner { margin-top:14px; padding:11px 13px; border-radius:10px; font-size:13.5px;
    display:none; }
  .banner.show { display:block; }
  .banner.bad { background:rgba(255,84,112,.14); box-shadow:inset 0 0 0 1px var(--bad);
    color:#ffd0da; }
  .banner.ok { background:rgba(57,217,138,.12); box-shadow:inset 0 0 0 1px var(--ok); color:#c8f7de; }
  a.dash { color:var(--x); text-decoration:none; font-weight:600; }
  a.dash:hover { text-decoration:underline; }
  .hint { color:var(--muted); font-size:12.5px; margin-top:8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Tic-Tac-Toe, verified live</h1>
  <p class="sub">Two players, one keyboard. Every move is checked against four
     laws by a deterministic monitor &mdash;
     watch it on the <a class="dash" href="__DASHBOARD_URL__" target="_blank">behave-rv dashboard &nearr;</a></p>

  <div class="grid">
    <div class="card">
      <div class="status"><span id="dot" class="dot"></span><span id="turn">&nbsp;</span></div>
      <div class="board" id="board"></div>
      <div class="row">
        <button class="act" id="new">New game</button>
        <span class="hint" id="gid"></span>
      </div>
      <div class="banner" id="banner"></div>
    </div>

    <div>
      <div class="card">
        <h2>The four laws</h2>
        <div class="law"><b>1 &middot; Strict alternation</b>
          <span>after X moves, the next move must be O &mdash; never twice in a row</span></div>
        <div class="law"><b>2 &middot; No move after finish</b>
          <span>once won or drawn, no further move may be made</span></div>
        <div class="law"><b>3 &middot; Every game finishes</b>
          <span>a game that starts must be won or drawn, never abandoned</span></div>
        <div class="law"><b>4 &middot; No orphan moves</b>
          <span>a move only happens after its game has started</span></div>
      </div>
      <div class="card" style="margin-top:16px">
        <h2>Demo &middot; inject a corrupted event</h2>
        <div class="row">
          <button class="danger" id="inj-double">Double move</button>
          <button class="danger" id="inj-after">Move after win</button>
          <button class="danger" id="inj-orphan">Orphan move</button>
        </div>
        <p class="hint">These bypass the game's own rules to push an illegal event
           straight to the monitor. Watch the matching policy turn red on the dashboard.</p>
      </div>
    </div>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const board = $('#board');
const cells = [];
for (let i=0;i<9;i++){
  const b = document.createElement('button');
  b.className='cell'; b.dataset.i=i;
  b.addEventListener('click',()=>move(i));
  board.appendChild(b); cells.push(b);
}
let state = null;

function render(s){
  state = s;
  s.board.forEach((v,i)=>{
    cells[i].textContent = v||'';
    cells[i].className = 'cell' + (v?(' '+v.toLowerCase()):'');
    cells[i].disabled = s.over || !!v;
  });
  const dot = $('#dot'), turn = $('#turn');
  if (s.over){
    dot.className='dot';
    turn.textContent = s.outcome==='draw' ? 'Draw - nobody wins'
                     : ('Game over - ' + (s.winner||'?') + ' wins');
  } else {
    dot.className='dot '+ (s.turn==='X'?'x':'o');
    turn.textContent = s.turn + ' to move';
  }
  $('#gid').textContent = 'game ' + s.game_id;
  $('#inj-after').disabled = !s.over;
  if (s.error){ banner(s.error,'bad'); }
}
function banner(msg,kind){
  const el = $('#banner');
  el.textContent = msg; el.className = 'banner show '+kind;
  clearTimeout(banner._t);
  banner._t = setTimeout(()=>{ el.className='banner'; }, 4000);
}
async function post(path,body){
  const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body||{})});
  return r.json();
}
async function move(i){
  if (state && (state.over || state.board[i])) return;
  render(await post('/api/move',{cell:i}));
}
$('#new').addEventListener('click', async ()=>{ render(await post('/api/new',{})); });
$('#inj-double').addEventListener('click', async ()=>{
  render(await post('/api/inject',{kind:'double'}));
  banner('Injected a double move - check law 1 on the dashboard','bad');
});
$('#inj-after').addEventListener('click', async ()=>{
  const s = await post('/api/inject',{kind:'after_win'});
  render(s);
  if(!s.error) banner('Injected a move after the finish - check law 2 on the dashboard','bad');
});
$('#inj-orphan').addEventListener('click', async ()=>{
  render(await post('/api/inject',{kind:'orphan'}));
  banner('Injected a move for a game that never started - check law 4 on the dashboard','bad');
});
(async ()=>{ const r = await fetch('/api/state'); render(await r.json()); })();
</script>
</body>
</html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Browser tic-tac-toe with live RV")
    ap.add_argument("--port", type=int, default=8804, help="game UI port")
    ap.add_argument("--dashboard-port", type=int, default=7104, help="dashboard port")
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry = build_registry()
    policies = load_policies(registry)

    start = time.time()
    clock = lambda: time.time() - start          # service-relative, readable times
    source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(CATALOG_PATH), app=[str(APP_PATH)])
    recorder = TraceRecorder(TRACE_PATH, clock=clock)
    service = TicTacToeService(
        lambda e: source.push(dashboard.tap(recorder(e))), clock=clock)

    dash_url = dashboard.start(port=args.dashboard_port, host=args.host)
    engine = Engine(policies, terminal_event_types={ENDED_TYPE}, grace=0)
    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    table = Table(service, dash_url)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(table))
    game_url = f"http://{args.host}:{args.port}"
    print(f"game:          {game_url}")
    print(f"live monitor:  {dash_url}")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        httpd.shutdown()
        recorder.close()
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
