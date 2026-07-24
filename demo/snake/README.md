# Snake, born monitorable

A browser Snake game with a [behave-rv](https://github.com/moraneus/behave-rv)
runtime monitor running beside it. Standard library only (plus behave-rv): the
game UI is an inline HTML/canvas page the app serves itself.

## Run it

```bash
pip install "behave-rv>=0.3.0"          # Python 3.10+

python live_monitor.py                  # game :8801, dashboard :7101
#   --game-port / --dashboard-port / --host to change

python demo.py                          # scripted games, prints every verdict
python demo.py --dashboard              # same, but also serve the live board

python monitoring/replay_check.py       # the exit-coded CI gate
```

Open the game URL and play with the arrow keys. Open the dashboard URL to watch
every policy as a card with its per-entity verdicts, each violation rendered as
the authored scenario with the failing step marked, the live event feed, and a
stability strip showing the code still matches the committed catalog.

## The three monitored rules (yours, in `monitoring/policies/`)

1. Once a game is over, no further moves or points are scored
   (`01_no_activity_after_game_over.feature`).
2. Every eaten food grows the snake within 2 seconds
   (`02_food_growth_within_2s.feature`).
3. A 180-degree reversal is never accepted
   (`03_no_reversal_accepted.feature`).

The engine enforces all three; the monitor verifies them independently. The
demo injects *corrupted* events - what a buggy or tampered build could emit -
to break each rule, so you see the monitor catch them.

## Layout

```
app/game.py        the game engine - the only file that emits Events
app/server.py      the browser front end (no instrumentation here)
live_monitor.py    live entry point: game + dashboard wired together
demo.py            scripted demo (no browser); records the demo trace
monitoring/        steps.py, policies/, catalog.json, STEPS.md, replay_check.py, traces/
```

## Modelling note

`game.over` is **not** a terminal event. A terminal would settle rule 1 as
satisfied the instant a game ended, making post-over corruption invisible (a
false green). Dead games are reclaimed by a quiescence TTL instead. See the
monitoring report for the trade-off.
