"""HTTP server for the Blackjack browser UI (standard library only).

Serves a single self-contained page (inline HTML/CSS/JS, no external assets)
and a tiny JSON action API. The handler only calls the injected
``BlackjackGame`` under a lock; all event emission happens inside the game,
so this module constructs no events and stays out of the monitored surface.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_server(game, host: str, port: int, dashboard_url: str):
    lock = threading.Lock()
    page = PAGE_HTML.replace("__DASHBOARD_URL__", dashboard_url)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):     # keep the console quiet
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/state":
                with lock:
                    self._json(game.state())
            else:
                self.send_error(404)

        def do_POST(self):
            actions = {"/new": game.new_hand, "/hit": game.hit,
                       "/stand": game.stand}
            action = actions.get(self.path)
            if action is None:
                self.send_error(404)
                return
            with lock:
                state = action()
            self._json(state)

    return ThreadingHTTPServer((host, port), Handler)


PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blackjack - monitored</title>
<style>
  :root { --felt:#0b6b3a; --felt2:#0a5730; --gold:#e8c05a; --ink:#0c1a12; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: radial-gradient(120% 90% at 50% -10%, var(--felt) 0%, var(--felt2) 55%, #063f22 100%);
         color:#f4f7f2; min-height:100vh; }
  header { display:flex; align-items:center; justify-content:space-between;
           padding:16px 22px; border-bottom:1px solid rgba(255,255,255,.12); }
  h1 { font-size:20px; margin:0; letter-spacing:.5px; }
  h1 span { color:var(--gold); }
  .dash { font-size:13px; color:#dfeee4; text-decoration:none; border:1px solid rgba(255,255,255,.25);
          padding:6px 12px; border-radius:8px; background:rgba(0,0,0,.18); }
  .dash:hover { background:rgba(0,0,0,.32); }
  main { max-width:820px; margin:0 auto; padding:26px 18px 60px; }
  .table { background:linear-gradient(180deg, rgba(0,0,0,.10), rgba(0,0,0,.28));
           border:1px solid rgba(255,255,255,.10); border-radius:20px; padding:26px;
           box-shadow: inset 0 2px 30px rgba(0,0,0,.35); }
  .row { margin:14px 0; }
  .row h2 { font-size:13px; text-transform:uppercase; letter-spacing:2px; margin:0 0 10px;
            color:#bfe6cd; font-weight:600; }
  .cards { display:flex; gap:10px; flex-wrap:wrap; min-height:104px; align-items:center; }
  .card { width:70px; height:100px; border-radius:10px; background:#fbfbf7; color:#111;
          display:flex; flex-direction:column; justify-content:space-between; padding:8px;
          font-weight:700; box-shadow:0 6px 14px rgba(0,0,0,.35); font-size:20px;
          animation: deal .28s ease; }
  .card.red { color:#c02626; }
  .card .b { align-self:flex-end; transform:rotate(180deg); }
  .card.back { background:repeating-linear-gradient(45deg,#7a1020,#7a1020 8px,#5f0b18 8px,#5f0b18 16px);
               color:transparent; }
  @keyframes deal { from { transform:translateY(-16px) rotate(-4deg); opacity:0; } }
  .tot { font-size:13px; color:#bfe6cd; margin-top:6px; min-height:18px; }
  .controls { display:flex; gap:12px; margin-top:22px; flex-wrap:wrap; }
  button { font:inherit; font-weight:700; border:none; border-radius:10px; padding:13px 20px;
           cursor:pointer; color:var(--ink); background:var(--gold); transition:transform .06s, filter .2s; }
  button.ghost { background:rgba(255,255,255,.14); color:#fff; }
  button:disabled { opacity:.4; cursor:not-allowed; }
  button:not(:disabled):active { transform:translateY(1px); }
  .status { margin-top:20px; display:flex; align-items:center; justify-content:space-between;
            gap:16px; flex-wrap:wrap; }
  .banner { font-size:22px; font-weight:800; min-height:30px; }
  .banner.win, .win { color:#8ff0ab; }
  .banner.lose, .lose { color:#ff9b9b; }
  .banner.push, .push { color:var(--gold); }
  .chips { font-size:15px; color:#dfeee4; }
  .chips b { color:var(--gold); }
  .hint { margin-top:14px; font-size:12.5px; color:#a9cdb8; line-height:1.5; }
  code { background:rgba(0,0,0,.3); padding:1px 6px; border-radius:5px; }
</style>
</head>
<body>
<header>
  <h1>♠ <span>Black</span>jack <span style="opacity:.6;font-size:13px">· born monitorable</span></h1>
  <a class="dash" href="__DASHBOARD_URL__" target="_blank">open RV dashboard ↗</a>
</header>
<main>
  <div class="table">
    <div class="row">
      <h2>Dealer</h2>
      <div class="cards" id="dealer"></div>
      <div class="tot" id="dealerTot"></div>
    </div>
    <div class="row">
      <h2>You</h2>
      <div class="cards" id="player"></div>
      <div class="tot" id="playerTot"></div>
    </div>
    <div class="status">
      <div class="banner" id="banner"></div>
      <div class="chips">chips: <b id="chips">-</b> · bet <span id="bet">-</span></div>
    </div>
    <div class="controls">
      <button id="btnNew">New hand</button>
      <button id="btnHit" class="ghost">Hit</button>
      <button id="btnStand" class="ghost">Stand</button>
    </div>
    <div class="hint">
      Every hand emits events to the monitor as it runs. Watch the four table
      rules verified live on the <a class="dash" style="border:none;padding:0"
      href="__DASHBOARD_URL__" target="_blank">RV dashboard</a>: no card after a
      stand, a bust never wins, settlement within 30 seconds, and no payout
      before settlement.
    </div>
  </div>
</main>
<script>
const $ = id => document.getElementById(id);
const SUIT_RED = new Set(["♥","♦"]);
function cardEl(c){
  const d = document.createElement("div");
  if (c === null){ d.className = "card back"; d.textContent = "?"; return d; }
  d.className = "card" + (SUIT_RED.has(c.suit) ? " red" : "");
  const t = c.rank + c.suit;
  d.innerHTML = '<div class="t">'+t+'</div><div class="b">'+t+'</div>';
  return d;
}
function render(s){
  const dealer = $("dealer"), player = $("player");
  dealer.innerHTML = ""; player.innerHTML = "";
  (s.player || []).forEach(c => player.appendChild(cardEl(c)));
  (s.dealer || []).forEach(c => dealer.appendChild(cardEl(c)));
  if (s.dealer_hidden) dealer.appendChild(cardEl(null));
  $("playerTot").textContent = s.player_total != null ? "total " + s.player_total : "";
  $("dealerTot").textContent = s.dealer_total != null
     ? (s.dealer_hidden ? "showing " + s.dealer_total : "total " + s.dealer_total) : "";
  $("chips").textContent = s.chips;
  $("bet").textContent = s.bet != null ? s.bet : "-";
  const b = $("banner");
  const acting = s.phase === "player";
  $("btnHit").disabled = !acting;
  $("btnStand").disabled = !acting;
  if (s.outcome){
    const label = {win:"You win!", lose:"Dealer wins", push:"Push"}[s.outcome];
    b.className = "banner " + s.outcome; b.textContent = label;
  } else if (s.phase === "idle"){
    b.className = "banner"; b.textContent = "Press New hand to deal.";
  } else { b.className = "banner"; b.textContent = ""; }
}
async function act(path){
  const r = await fetch(path, {method:"POST"});
  render(await r.json());
}
$("btnNew").onclick = () => act("/new");
$("btnHit").onclick = () => act("/hit");
$("btnStand").onclick = () => act("/stand");
fetch("/state").then(r => r.json()).then(render);
</script>
</body>
</html>"""
