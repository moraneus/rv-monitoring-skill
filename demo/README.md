# Example projects

Ten small applications built with the rv skill, each shipping with its own
behave-rv runtime monitor and a live dashboard. They are here to be read and
run: every one has its monitored policies in `monitoring/policies/`, its
instrumentation in `app/`, a committed two-sided contract in
`monitoring/catalog.json`, and a deterministic replay gate. CI runs each
demo's gates against the published `behave-rv` on every push.

## Five services

| Demo | What it monitors |
|---|---|
| **lending** | a library lending service - loans borrowed, renewed, returned, or reported lost |
| **parcels** | a pre-existing parcel tracker, made monitorable without changing its behaviour |
| **bookings** | a fitness-studio class-bookings flow, designed through the `/rv` interview |
| **devices** | an IoT fleet tracker - device lifecycles plus independent sensor feeds |
| **payments** | a payment tracker - authorize, capture, dispute, refund, close |

## Five browser games

Each game serves its own inline HTML/JS UI (standard library only) and runs
its monitor alongside, with in-browser buttons to inject a corrupted event
so you can watch a policy card turn red live.

| Demo | What it monitors |
|---|---|
| **snake** | no play after game-over; food is followed by growth; no 180° reversal |
| **blackjack** | no card after a stand; a bust never wins; payout only after settlement; a loser is never paid |
| **minesweeper** | no reveal after a mine explodes; no cell revealed twice; flags never outnumber mines |
| **tictactoe** | strict turn alternation; no move after the game is decided; every game finishes |
| **memory** | a matched card is never re-flipped; an attempt resolves within 3 seconds; nothing after completion |

## Running a demo

```bash
pip install behave-rv        # >= 0.3.1, Python 3.10+
cd demo/<name>

# services: drive the live dashboard
python demo.py               # lending, parcels, devices, payments
python live_monitor.py       # bookings

# games: serve the browser game + its dashboard
python demo.py               # snake, blackjack, minesweeper, tictactoe
python server.py             # memory
```

The live dashboard shows every policy as a card with its per-entity verdicts,
the authored scenario replayed with the failing step marked for each
violation, a live event feed, and a strip showing whether the running code
still matches the committed contract. The deterministic gates each demo ships:

```bash
python monitoring/replay_check.py
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/<service>.py \
  --fail-on-app-risk --trace monitoring/traces/<trace>.jsonl
```

## See the monitor find real bugs

The [`experiment/`](../experiment/index.html) folder is an offline report
that takes these ten apps, plants realistic bugs in their code, and shows,
demo by demo, exactly how the runtime monitor did or did not catch each one.
Open `experiment/index.html` in a browser.
