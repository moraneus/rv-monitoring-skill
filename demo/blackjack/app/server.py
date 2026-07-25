"""Live Blackjack: a browser game whose every move is verified at runtime.

Two servers come up:

* the game UI on ``--game-port`` (default 8802) - play in the browser;
* the behave-rv dashboard on ``--dash-port`` (default 7102) - watch your
  four table rules enforced live, per hand, as you play.

Standard library only (plus behave-rv). The UI is a single self-contained HTML
page served by this process; no CDNs, no build step.

    python app/server.py [--game-port 8802] [--dash-port 7102]

Every game action emits events through one chain -
``source.push(dashboard.tap(recorder(event)))`` - so the same event reaches
the engine, the dashboard's live feed, and a replayable trace at once.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.events.event import Event                          # noqa: E402
from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.subscription import QueueSource     # noqa: E402
from behave_rv.events.sources.replay import TraceRecorder         # noqa: E402
from behave_rv.dashboard import Dashboard                         # noqa: E402

from steps import build_registry, load_policies                   # noqa: E402
from app.blackjack import (BlackjackTable, SOURCE, DEALT, STOOD,   # noqa: E402
                           BUSTED, SETTLED, PAYOUT, CLOSED, BET)

TERMINAL_TYPES = {CLOSED}


class Game:
    """Owns the table, the emit chain, and the live monitor wiring."""

    def __init__(self, dash_port: int):
        self.registry = build_registry()
        self.policies = load_policies(self.registry)
        self.source = QueueSource()
        self.dashboard = Dashboard(self.policies, registry=self.registry,
                                   catalog=str(ROOT / "monitoring" / "catalog.json"),
                                   app=[str(ROOT / "app" / "blackjack.py")])
        self._start = time.time()
        self._clock = lambda: time.time() - self._start
        trace = ROOT / "monitoring" / "traces" / "live_session.jsonl"
        trace.unlink(missing_ok=True)          # fresh trace per process
        self.recorder = TraceRecorder(str(trace), clock=self._clock)
        self._emit = lambda e: self.source.push(self.dashboard.tap(self.recorder(e)))
        self.table = BlackjackTable(self._emit, clock=self._clock)
        self._lock = threading.Lock()
        self._cheat_n = 0
        self._last_t = 0.0

        self.dash_url = self.dashboard.start(port=dash_port)
        self.engine = Engine(self.policies, terminal_event_types=TERMINAL_TYPES,
                             grace=0.5)   # grace < the 30s deadline (live rule)
        threading.Thread(
            target=lambda: self.engine.run(self.source, sink=self.dashboard.sink),
            daemon=True).start()

    def _raw_time(self) -> float:
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        return t

    def _raw(self, ev_type: str, hand_id: str, payload: dict) -> None:
        self._emit(Event(ev_type, self._raw_time(), {"hand_id": hand_id},
                         payload, SOURCE))

    # --- player actions (fair game) ---------------------------------------
    def new_hand(self) -> dict:
        with self._lock:
            return self.table.new_hand()

    def hit(self) -> dict:
        with self._lock:
            return self.table.hit()

    def stand(self) -> dict:
        with self._lock:
            return self.table.stand()

    # --- demo cheat injection (clearly labelled in the UI) ------------------
    def inject_cheat(self, kind: str) -> dict:
        """Push a self-contained CORRUPTED hand onto the stream so the live
        dashboard is seen catching it. Does not touch the real game state."""
        with self._lock:
            self._cheat_n += 1
            hid = f"H-cheat-{self._cheat_n}"
            if kind == "stand_card":
                self._raw(DEALT, hid, {"card": "KS", "total": 10, "to": "player"})
                self._raw(DEALT, hid, {"card": "8H", "total": 18, "to": "player"})
                self._raw(STOOD, hid, {"total": 18})
                self._raw(DEALT, hid, {"card": "3D", "total": 21, "to": "player"})
                self._raw(SETTLED, hid, {"outcome": "win"})
                self._raw(PAYOUT, hid, {"amount": 2 * BET})
                self._raw(CLOSED, hid, {"outcome": "win"})
                msg = "injected: a card dealt after stand (rule 1)"
            elif kind == "bust_win":
                self._raw(DEALT, hid, {"card": "KS", "total": 10, "to": "player"})
                self._raw(DEALT, hid, {"card": "9H", "total": 19, "to": "player"})
                self._raw(DEALT, hid, {"card": "7D", "total": 26, "to": "player"})
                self._raw(BUSTED, hid, {"total": 26})
                self._raw(SETTLED, hid, {"outcome": "win"})
                self._raw(PAYOUT, hid, {"amount": 2 * BET})
                self._raw(CLOSED, hid, {"outcome": "win"})
                msg = "injected: a busted hand settled as a win (rule 2)"
            elif kind == "loser_paid":
                self._raw(DEALT, hid, {"card": "KS", "total": 10, "to": "player"})
                self._raw(DEALT, hid, {"card": "7H", "total": 17, "to": "player"})
                self._raw(STOOD, hid, {"total": 17})
                self._raw(SETTLED, hid, {"outcome": "lose"})
                self._raw(PAYOUT, hid, {"amount": 2 * BET})
                self._raw(CLOSED, hid, {"outcome": "lose"})
                msg = "injected: a losing hand paid out (rule 5)"
            else:
                msg = "unknown cheat"
            return {"cheat": hid, "message": msg}

    def shutdown(self) -> None:
        try:
            self.recorder.close()
        finally:
            self.source.close()
            self.dashboard.stop()


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blackjack - runtime verified</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, sans-serif;
         background: radial-gradient(circle at 50% 0%, #17603f, #0c3b28 60%, #08251a);
         color: #f3f7f4; min-height: 100vh; }
  header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
           padding: 18px 24px; border-bottom: 1px solid rgba(255,255,255,.12); }
  h1 { margin: 0; font-size: 20px; letter-spacing: .3px; }
  header .sub { color: #bfe3d0; font-size: 13px; }
  main { max-width: 760px; margin: 0 auto; padding: 24px; }
  .felt { background: rgba(0,0,0,.22); border: 1px solid rgba(255,255,255,.1);
          border-radius: 16px; padding: 22px; box-shadow: 0 8px 40px rgba(0,0,0,.35); }
  .row { margin-bottom: 20px; }
  .label { font-size: 12px; text-transform: uppercase; letter-spacing: 1.2px;
           color: #9fd3b6; margin-bottom: 8px; }
  .cards { display: flex; gap: 10px; flex-wrap: wrap; min-height: 74px; }
  .card { width: 52px; height: 74px; border-radius: 8px; background: #fbfbf7;
          color: #14181b; display: flex; align-items: center; justify-content: center;
          font-size: 20px; font-weight: 700; box-shadow: 0 3px 8px rgba(0,0,0,.4);
          position: relative; }
  .card.red { color: #c0392b; }
  .card.back { background: repeating-linear-gradient(45deg,#7a1f2b,#7a1f2b 6px,#5c141d 6px,#5c141d 12px);
               color: transparent; }
  .total { font-weight: 700; color: #eafff2; }
  .status { min-height: 26px; font-size: 16px; font-weight: 600; margin: 6px 0 16px; }
  .win { color: #7ff0a8; } .lose { color: #ff9c8f; } .push { color: #ffe08a; }
  .controls { display: flex; gap: 10px; flex-wrap: wrap; }
  button { font: inherit; font-weight: 600; padding: 10px 18px; border-radius: 10px;
           border: 1px solid rgba(255,255,255,.18); background: #1f7a52; color: #fff;
           cursor: pointer; transition: transform .05s, background .15s; }
  button:hover:not(:disabled) { background: #269563; }
  button:active:not(:disabled) { transform: translateY(1px); }
  button:disabled { opacity: .4; cursor: not-allowed; }
  button.ghost { background: transparent; }
  .chips { margin-left: auto; font-weight: 700; color: #ffe08a; }
  .cheats { margin-top: 22px; padding-top: 18px; border-top: 1px dashed rgba(255,255,255,.16); }
  .cheats .label { color: #ffb4a2; }
  button.cheat { background: #7a2f2f; border-color: rgba(255,120,120,.4); }
  button.cheat:hover { background: #9b3a3a; }
  .monitor { margin-top: 20px; font-size: 13px; color: #bfe3d0; }
  .monitor a { color: #7ff0a8; }
  .toast { margin-top: 10px; min-height: 20px; font-size: 13px; color: #ffcf9a; }
</style></head>
<body>
<header>
  <h1>&#9824; Blackjack</h1>
  <span class="sub">player vs dealer &middot; single deck &middot; every hand verified at runtime</span>
</header>
<main>
  <div class="felt">
    <div class="row">
      <div class="label">Dealer <span id="dtotal" class="total"></span></div>
      <div id="dealer" class="cards"></div>
    </div>
    <div class="row">
      <div class="label">You <span id="ptotal" class="total"></span></div>
      <div id="player" class="cards"></div>
    </div>
    <div id="status" class="status"></div>
    <div class="controls">
      <button id="hit">Hit</button>
      <button id="stand">Stand</button>
      <button id="new">New hand</button>
      <span class="chips">Chips: <span id="chips">100</span></span>
    </div>
    <div class="cheats">
      <div class="label">Injected cheats (watch the monitor catch them)</div>
      <div class="controls">
        <button class="cheat" data-kind="stand_card">Deal a card after stand</button>
        <button class="cheat" data-kind="bust_win">Settle a bust as a win</button>
        <button class="cheat" data-kind="loser_paid">Pay a losing hand</button>
      </div>
      <div id="toast" class="toast"></div>
    </div>
  </div>
  <div class="monitor">
    Live monitor dashboard: <a id="dash" href="#" target="_blank"></a> &mdash;
    every rule is a card there, red when a hand violates it, with the failing
    step and the deciding events shown.
  </div>
</main>
<script>
const RED = new Set(["H","D"]);
let chips = 100, lastHand = null;

function cardEl(c) {
  const d = document.createElement("div");
  if (c === "??") { d.className = "card back"; d.textContent = "?"; return d; }
  const suit = c.slice(-1), rank = c.slice(0, -1);
  const glyph = {S:"\\u2660", H:"\\u2665", D:"\\u2666", C:"\\u2663"}[suit] || "";
  d.className = "card" + (RED.has(suit) ? " red" : "");
  d.textContent = rank + glyph;
  return d;
}
function render(s) {
  const dealer = document.getElementById("dealer");
  const player = document.getElementById("player");
  dealer.innerHTML = ""; player.innerHTML = "";
  (s.dealer || []).forEach(c => dealer.appendChild(cardEl(c)));
  (s.player || []).forEach(c => player.appendChild(cardEl(c)));
  document.getElementById("ptotal").textContent =
      s.player_total ? "(" + s.player_total + ")" : "";
  document.getElementById("dtotal").textContent =
      (s.dealer_total != null) ? "(" + s.dealer_total + ")" : "";
  const st = document.getElementById("status");
  const playing = s.status === "playing";
  if (s.status === "settled" || s.status === "busted") {
    const o = s.outcome;
    st.className = "status " + (o === "win" ? "win" : o === "push" ? "push" : "lose");
    st.textContent = o === "win" ? "You win!" : o === "push" ? "Push."
                   : (s.status === "busted" ? "Bust - you lose." : "You lose.");
    if (lastHand !== s.hand_id) {
      lastHand = s.hand_id;
      chips += o === "win" ? 10 : o === "push" ? 0 : -10;
      document.getElementById("chips").textContent = chips;
    }
  } else if (s.status === "idle") {
    st.className = "status"; st.textContent = "Press New hand to deal.";
  } else {
    st.className = "status"; st.textContent = "Your move.";
  }
  document.getElementById("hit").disabled = !playing;
  document.getElementById("stand").disabled = !playing;
}
async function act(path) {
  const r = await fetch(path, {method: "POST"});
  render(await r.json());
}
async function boot() {
  const r = await fetch("/api/state"); const s = await r.json();
  const a = document.getElementById("dash");
  a.textContent = s.dash_url; a.href = s.dash_url;
  render(s);
}
document.getElementById("hit").onclick = () => act("/api/hit");
document.getElementById("stand").onclick = () => act("/api/stand");
document.getElementById("new").onclick = () => act("/api/new");
document.querySelectorAll("button.cheat").forEach(b => b.onclick = async () => {
  const r = await fetch("/api/cheat?kind=" + b.dataset.kind, {method: "POST"});
  const j = await r.json();
  document.getElementById("toast").textContent =
      j.message + " - see it flagged on the monitor.";
});
boot();
</script>
</body></html>
"""


def make_handler(game: Game):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):    # quiet
            pass

        def _send(self, code, body, ctype):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, obj):
            self._send(200, json.dumps(obj), "application/json")

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path.startswith("/api/state"):
                s = game.table.state()
                s["dash_url"] = game.dash_url
                self._json(s)
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path.startswith("/api/new"):
                self._json(game.new_hand())
            elif self.path.startswith("/api/hit"):
                self._json(game.hit())
            elif self.path.startswith("/api/stand"):
                self._json(game.stand())
            elif self.path.startswith("/api/cheat"):
                from urllib.parse import urlparse, parse_qs
                kind = parse_qs(urlparse(self.path).query).get("kind", ["stand_card"])[0]
                self._json(game.inject_cheat(kind))
            else:
                self._send(404, "not found", "text/plain")

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-port", type=int, default=8802)
    ap.add_argument("--dash-port", type=int, default=7102)
    args = ap.parse_args()

    game = Game(args.dash_port)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.game_port), make_handler(game))
    print(f"blackjack game:  http://127.0.0.1:{args.game_port}")
    print(f"live monitor:    {game.dash_url}")
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        game.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
