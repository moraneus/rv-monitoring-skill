# Minesweeper, born monitorable

Browser Minesweeper (8x8, 10 mines) with runtime verification built in. You
play in the browser; a [behave-rv](https://github.com/moraneus/behave-rv)
dashboard runs alongside and checks every move against three rules you own.

## Run it

Use the provided venv's Python for every command.

```bash
python app/server.py                 # --game-port 8803  --dash-port 7103
```

It prints two URLs:

* **game**: `http://127.0.0.1:8803` - left-click reveals, right-click flags,
  "New game" starts a fresh board.
* **live monitor**: `http://127.0.0.1:7103` - open it in a second window. Each
  of your three rules is a card; you see per-board (and per-square) verdicts,
  the rendered explanation for any violation, the live event feed, and a
  stability strip confirming the running code still matches the committed
  contract.

Play emits events to the monitor as it happens. The board's own guards keep
honest play legal, so in the browser the cards stay green - the monitor is the
independent check for a stream that bypasses those guards.

## The scripted demo (no browser)

```bash
python demo.py
```

Plays a healthy board and an honest loss (zero violations), then injects three
CORRUPTED event streams - a reveal after the boom, a double reveal of one
square, and a flag count above the mine budget - and prints each caught
violation as your own scenario replayed with the failing step marked.

## The rules (in `monitoring/policies/`)

1. `01_no_reveal_after_explosion.feature` - once a mine explodes, no cell is
   revealed on that board again.
2. `02_no_double_reveal.feature` - no square is revealed twice (each square of
   each board is its own monitored entity).
3. `03_flags_within_budget.feature` - planted flags never exceed the mine count.

## The gates

```bash
python -m behave_rv catalog diff --steps monitoring/steps.py \
  --catalog monitoring/catalog.json --policies monitoring/policies \
  --app app/game.py --fail-on-app-risk --trace monitoring/traces/representative.jsonl
python monitoring/replay_check.py
```

The first checks the code still matches the committed two-sided contract; the
second replays scripted traffic (healthy + the three cheats) and asserts the
verdict counts. Both exit 0 when green.

## Layout

```
app/game.py        the game engine, instrumented (emits events at each transition)
app/server.py      http.server board UI + dashboard, wired to a live engine thread
demo.py            scripted boards incl. injected cheats, no browser
monitoring/        steps.py (vocabulary), policies/, catalog.json, STEPS.md,
                   replay_check.py (gate), traces/, SUGGESTED_POLICIES.md
```
