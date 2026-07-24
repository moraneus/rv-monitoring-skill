"""The Memory game as a live, monitored web app (standard library only).

    python app/server.py [--game-port 8805] [--dash-port 7105]

Serves a browser game on ``--game-port`` and the behave-rv live dashboard on
``--dash-port``. Every player action flows through the real ``MemoryGame`` and
emits events into the engine; open the dashboard to watch the three policies
verify the running game in the user's own words.

Wiring (the rv live-view pattern):

    emit = lambda e: source.push(dashboard.tap(recorder(e)))
    engine.run(source, sink=dashboard.sink)     # in a background thread

The ``/api/cheat`` endpoint injects a CORRUPTED event directly - the kind of
untrusted, out-of-contract input the monitor exists to catch. It is fault
injection, not part of the game's legitimate emission surface (``app/game.py``,
the only file the catalog's ``--app`` covers), so a violation appears on the
dashboard without the game logic ever producing it.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.event import Event                          # noqa: E402
from behave_rv.events.sources.subscription import QueueSource     # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder         # noqa: E402
from behave_rv.dashboard import Dashboard                         # noqa: E402

from app.game import (                                            # noqa: E402
    MemoryGame, live_clock, new_order,
    CARD_FLIP, CARD_MATCHED, GAME_ACTION, ATTEMPT_PENDING, SOURCE,
)
from steps import build_registry, load_policies                  # noqa: E402


class GameManager:
    """Holds every live game; all share one emit chain and one clock."""

    def __init__(self, emit, clock):
        self._emit = emit
        self._clock = clock
        self._games: dict[str, MemoryGame] = {}
        self._flipped: dict[str, set] = {}   # server-side flip history per game
        self._seq = 0
        self._lock = threading.Lock()

    def new_game(self, seed=None) -> MemoryGame:
        with self._lock:
            self._seq += 1
            game_id = f"game-{self._seq}"
            game = MemoryGame(game_id, self._emit, self._clock,
                              order=new_order(seed))
            self._games[game_id] = game
            self._flipped[game_id] = set()
        game.start()
        return game

    def get(self, game_id) -> MemoryGame | None:
        return self._games.get(game_id)

    def flip(self, game_id, position) -> dict | None:
        game = self._games.get(game_id)
        if game is None:
            return None
        if position is not None:
            self._flipped.setdefault(game_id, set()).add(position)
        return game.flip(position)

    # -- fault injection (corrupted events, out of the game's contract) -------
    def cheat(self, game_id, kind) -> dict:
        game = self._games.get(game_id)
        if game is None:
            return {"error": "no such game"}
        if kind == "reflip":
            matched = [i for i, c in game.cards.items() if c.matched]
            if not matched:
                return {"error": "no matched card yet - match a pair first"}
            pos = matched[0]
            self._emit(Event(CARD_FLIP, self._clock(),
                             {"game_id": game_id, "position": pos},
                             {"symbol": game.cards[pos].symbol,
                              "attempt_id": f"{game_id}-cheat"}, SOURCE))
            return {"ok": "re-flipped a matched card - rule 1 should violate"}
        if kind == "hang":
            self._emit(Event(ATTEMPT_PENDING, self._clock(),
                             {"attempt_id": f"{game_id}-hang-{time.time():.0f}"},
                             {"game_id": game_id, "first": 0, "second": 1},
                             SOURCE))
            return {"ok": "left an attempt hanging - rule 2 violates in 3s"}
        if kind == "after_complete":
            if not game.complete:
                return {"error": "finish the game first, then inject"}
            self._emit(Event(GAME_ACTION, self._clock(),
                             {"game_id": game_id}, {"kind": "ghost"}, SOURCE))
            return {"ok": "acted after completion - rule 3 should violate"}
        if kind == "phantom_match":
            # a card.matched for a card that was never flipped in this game -
            # a match out of nowhere. Pick a never-flipped, unmatched position.
            flipped = self._flipped.get(game_id, set())
            fresh = [i for i, c in game.cards.items()
                     if not c.matched and i not in flipped]
            pos = fresh[0] if fresh else 99   # 99 = a card that does not exist
            self._emit(Event(CARD_MATCHED, self._clock(),
                             {"game_id": game_id, "position": pos},
                             {"symbol": "ghost", "attempt_id": f"{game_id}-phantom"},
                             SOURCE))
            return {"ok": "reported a match for a never-flipped card - rule 4 "
                          "should violate"}
        return {"error": f"unknown cheat {kind!r}"}


def build_handler(manager: GameManager, dash_url: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # quiet

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj))

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, PAGE.replace("__DASH_URL__", dash_url),
                                  "text/html; charset=utf-8")
            if self.path.startswith("/api/state"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                game = manager.get((qs.get("game_id") or [""])[0])
                if game is None:
                    return self._json(404, {"error": "no such game"})
                return self._json(200, game.view("state"))
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            try:
                body = self._read_json()
            except json.JSONDecodeError:
                return self._json(400, {"error": "bad json"})
            if self.path == "/api/new":
                game = manager.new_game(seed=body.get("seed"))
                return self._json(200, game.view("new"))
            if self.path == "/api/flip":
                view = manager.flip(body.get("game_id"), body.get("position"))
                if view is None:
                    return self._json(404, {"error": "no such game"})
                return self._json(200, view)
            if self.path == "/api/cheat":
                result = manager.cheat(body.get("game_id"), body.get("kind"))
                code = 200 if "ok" in result else 400
                return self._json(code, result)
            return self._json(404, {"error": "not found"})

    return Handler


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memory - monitored by behave-rv</title>
<style>
  :root {
    --bg:#0f1220; --panel:#1a1f36; --ink:#e8ecff; --muted:#8b93b8;
    --accent:#6ea8fe; --good:#3ddc97; --bad:#ff6b81; --card:#2a3157;
    --card2:#343c6b; --gold:#f4c95d;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    background:radial-gradient(1200px 800px at 70% -10%,#1c2445,#0f1220);
    color:var(--ink); min-height:100vh;
  }
  header {
    display:flex; align-items:center; gap:16px; flex-wrap:wrap;
    padding:18px 24px; border-bottom:1px solid #262c4d;
  }
  header h1 { font-size:20px; margin:0; letter-spacing:.3px; }
  header .tag { color:var(--muted); font-size:13px; }
  .dash-link {
    margin-left:auto; font-size:13px; color:var(--accent);
    text-decoration:none; border:1px solid #33407a; padding:7px 12px;
    border-radius:8px; background:#141a33;
  }
  .dash-link:hover { background:#1b2547; }
  main {
    display:grid; grid-template-columns:minmax(320px,520px) minmax(280px,1fr);
    gap:24px; padding:24px; max-width:1100px; margin:0 auto; align-items:start;
  }
  @media (max-width:820px){ main{ grid-template-columns:1fr; } }
  .panel {
    background:linear-gradient(180deg,#1c2140,#171b31);
    border:1px solid #2a3157; border-radius:16px; padding:20px;
  }
  .board {
    display:grid; grid-template-columns:repeat(4,1fr); gap:12px;
  }
  .card {
    aspect-ratio:1; border:none; border-radius:14px; cursor:pointer;
    font-size:36px; display:flex; align-items:center; justify-content:center;
    background:linear-gradient(160deg,var(--card2),var(--card));
    color:transparent; transition:transform .18s, background .2s, box-shadow .2s;
    box-shadow:inset 0 -3px 0 rgba(0,0,0,.25); position:relative; user-select:none;
  }
  .card::after {
    content:"?"; color:#5b6499; font-size:26px; font-weight:700;
    position:absolute;
  }
  .card.up, .card.matched { color:var(--ink); }
  .card.up { background:linear-gradient(160deg,#3b467e,#2f3766); }
  .card.up::after, .card.matched::after { content:""; }
  .card.matched {
    background:linear-gradient(160deg,#1f6f52,#175a41);
    box-shadow:inset 0 0 0 2px var(--good), inset 0 -3px 0 rgba(0,0,0,.25);
    cursor:default;
  }
  .card:disabled { cursor:default; }
  .controls { display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }
  button.btn {
    font:inherit; font-size:14px; padding:9px 14px; border-radius:10px;
    border:1px solid #3a4680; background:#20264a; color:var(--ink);
    cursor:pointer;
  }
  button.btn:hover { background:#283163; }
  button.btn.primary { background:var(--accent); color:#0b1020; border-color:transparent; font-weight:600; }
  button.btn.primary:hover { filter:brightness(1.08); }
  .status { margin-top:16px; font-size:14px; color:var(--muted); min-height:20px; }
  .status b { color:var(--ink); }
  .rules h2, .cheats h2 { font-size:14px; text-transform:uppercase; letter-spacing:.6px;
    color:var(--muted); margin:0 0 12px; }
  .rule { padding:12px 14px; border:1px solid #2a3157; border-radius:12px;
    margin-bottom:10px; background:#151a30; }
  .rule .n { color:var(--gold); font-weight:700; margin-right:6px; }
  .rule small { color:var(--muted); display:block; margin-top:4px; }
  .cheats { margin-top:20px; }
  .cheats .row { display:flex; gap:10px; flex-wrap:wrap; }
  .cheats button { border-color:#5a2b3a; background:#2a1620; color:#ffb3c0; }
  .cheats button:hover { background:#3a1d2b; }
  .note { font-size:12.5px; color:var(--muted); margin-top:12px; line-height:1.5; }
  .flash { color:var(--bad); }
  .flash.ok { color:var(--good); }
</style>
</head>
<body>
<header>
  <h1>Memory</h1>
  <span class="tag">4x4 pairs, verified live by behave-rv</span>
  <a class="dash-link" href="__DASH_URL__" target="_blank">Open the live monitor &#8599;</a>
</header>
<main>
  <section class="panel">
    <div class="board" id="board"></div>
    <div class="controls">
      <button class="btn primary" id="new">New game</button>
      <span class="status" id="status">Loading&hellip;</span>
    </div>
    <div class="cheats">
      <h2>Inject a corrupted event</h2>
      <div class="row">
        <button class="btn" data-cheat="reflip">Re-flip a matched card</button>
        <button class="btn" data-cheat="hang">Leave an attempt hanging</button>
        <button class="btn" data-cheat="after_complete">Act after complete</button>
        <button class="btn" data-cheat="phantom_match">Report a phantom match</button>
      </div>
      <div class="note" id="cheatnote">These send events the game itself never would.
        Watch a policy card on the monitor turn red with the counterexample.</div>
    </div>
  </section>

  <aside class="panel rules">
    <h2>The rules being verified</h2>
    <div class="rule"><span class="n">1</span>A matched card is never flipped again.
      <small>Given a card is matched / Then a card is flipped never happens</small></div>
    <div class="rule"><span class="n">2</span>An attempt resolves within 3 seconds.
      <small>When an attempt is ready / Then an attempt is resolved within "3" seconds</small></div>
    <div class="rule"><span class="n">3</span>Nothing happens after the game is complete.
      <small>Given the game is complete / Then a game action occurs never happens</small></div>
    <div class="rule"><span class="n">4</span>Every matched card was flipped first.
      <small>When a card is matched / Then a card is flipped before</small></div>
    <div class="note">Every click flows through the real game, which emits events to
      the monitor. The dashboard shows each rule as a card with its per-entity
      verdicts and, on a violation, your own scenario replayed with the real events.</div>
  </aside>
</main>

<script>
const SYM = {fox:"🦊",owl:"🦉",bee:"🐝",cat:"🐱",
             koi:"🐟",elk:"🦌",ram:"🐏",jay:"🐦"};
let state=null, locked=false;

async function api(path, body){
  const r = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body||{})});
  return r.json();
}
function setStatus(html){ document.getElementById("status").innerHTML = html; }
function render(){
  const board = document.getElementById("board");
  board.innerHTML = "";
  state.cards.forEach(c => {
    const b = document.createElement("button");
    b.className = "card" + (c.matched ? " matched" : (c.symbol ? " up" : ""));
    b.textContent = c.symbol ? (SYM[c.symbol]||c.symbol) : "";
    b.disabled = locked || c.matched || !!c.symbol;
    b.onclick = () => flip(c.position);
    board.appendChild(b);
  });
  const done = state.complete;
  setStatus(`Pairs found <b>${state.pairs_found}/${state.pairs_total}</b>` +
            (done ? " &mdash; <b>complete!</b>" : ""));
}
async function flip(pos){
  if(locked) return;
  locked = true;
  state = await api("/api/flip", {game_id:state.game_id, position:pos});
  render();
  if(state.phase === "mismatched"){
    setTimeout(async () => {
      state = await api("/api/flip", {game_id:state.game_id, position:null});
      locked = false; render();
    }, 900);
  } else {
    locked = false; render();
  }
}
async function newGame(){
  locked = false;
  state = await api("/api/new", {});
  render();
}
document.getElementById("new").onclick = newGame;
document.querySelectorAll("[data-cheat]").forEach(btn => {
  btn.onclick = async () => {
    if(!state) return;
    const r = await api("/api/cheat", {game_id:state.game_id, kind:btn.dataset.cheat});
    const el = document.getElementById("cheatnote");
    const msg = r.ok || r.error;
    el.innerHTML = `<span class="flash ${r.ok?'ok':''}">${msg}</span>`;
    // refresh board (a re-flip cheat does not change the real board state)
    setTimeout(()=>{ el.innerHTML = "These send events the game itself never would. "+
      "Watch a policy card on the monitor turn red with the counterexample."; }, 5000);
  };
});
newGame();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-port", type=int, default=8805)
    ap.add_argument("--dash-port", type=int, default=7105)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    source = QueueSource()
    clock = live_clock()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "game.py")])
    recorder = TraceRecorder(str(ROOT / "monitoring" / "traces" / "live_session.jsonl"),
                             clock=clock)

    def emit(event: Event) -> None:
        source.push(dashboard.tap(recorder(event)))

    manager = GameManager(emit, clock)

    # grace (reorder window) must stay BELOW the smallest within deadline (3s),
    # or a response can still be buffered when the live wall-clock timer fires
    # and a resolved attempt reads as a false timeout. Events are emitted in
    # monotonic timestamp order, so a small window is safe.
    engine = Engine(policies, terminal_event_types={"attempt.resolved"}, grace=0.5)
    threading.Thread(target=engine.run, args=(source,),
                     kwargs={"sink": dashboard.sink}, daemon=True).start()

    dash_url = dashboard.start(port=args.dash_port, host=args.host)

    handler = build_handler(manager, dash_url)
    httpd = ThreadingHTTPServer((args.host, args.game_port), handler)
    game_url = f"http://{args.host}:{args.game_port}"
    print(f"Memory game:  {game_url}")
    print(f"Live monitor: {dash_url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.shutdown()
        source.close()
        recorder.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
