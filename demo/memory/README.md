# Memory pairs, verified live by behave-rv

A browser Memory game (4x4 grid, 8 pairs) that ships with runtime
verification: every action the game takes emits an event to a deterministic
behave-rv monitor that checks three rules, in your own words, against the live
event stream and shows a violation as your rule replayed as a counterexample.

Standard library only, plus `behave-rv` (>= 0.3.0, Python 3.10+).

## Run the live game + dashboard

```bash
python app/server.py                 # game on :8805, monitor on :7105
# or choose ports:
python app/server.py --game-port 8805 --dash-port 7105
```

Open the game at http://127.0.0.1:8805 and the live monitor at
http://127.0.0.1:7105 (there is a link in the game header). Play; the monitor
shows each rule as a card with its per-entity verdicts, a live event feed, and
a stability strip confirming the code still matches the committed contract.

The game page also has three **Inject a corrupted event** buttons. They send
events the game itself never would (a re-flip of a matched card, a hanging
attempt, an action after completion) - watch the matching policy card on the
monitor turn red with the counterexample. This is the untrusted input the
monitor exists to catch.

## Scripted demo (no browser)

```bash
python demo.py                       # live via the dashboard on :7105
python demo.py --no-dashboard        # console only, no web server
python demo.py --hold                # keep the dashboard open afterwards
```

Plays two healthy games, then injects the three cheats, and prints each
violation with its rendered scenario. The hanging attempt violates via the
live 3-second deadline timer.

## The replay gate (exit-coded)

```bash
python monitoring/replay_check.py    # exit 0 clean, exit 1 on drift
```

Deterministic scripted traffic (fake clock) through the real game and policies,
with pinned expectations: two healthy games (zero violations) plus one fault
per rule (three violations).

## The rules being verified

| # | Rule | Form | Correlation key |
|---|------|------|-----------------|
| 1 | A matched card is never flipped again | scoped `never` | `(game_id, position)` |
| 2 | An attempt resolves within 3 seconds | `within` | `attempt_id` |
| 3 | Nothing happens after the game is complete | scoped `never` | `game_id` |
| 4 | Every matched card was flipped first | `before` | `(game_id, position)` |

The policies live in `monitoring/policies/`. The vocabulary they are written
from is documented (generated) in `monitoring/STEPS.md`.

## Layout

```
app/
  game.py        the game logic, instrumented (the only file the catalog's --app covers)
  server.py      http.server UI + JSON API + live monitor wiring
demo.py          scripted demo (healthy games + injected cheats)
monitoring/
  steps.py               the vocabulary (build_registry + load_policies)
  policies/              the three rules, one Feature per file
  catalog.json           the committed two-sided stability contract
  STEPS.md               generated vocabulary doc (do not hand-edit)
  SUGGESTED_POLICIES.md  proposals for extra coverage (you decide)
  generate_steps_doc.py  regenerates STEPS.md
  replay_check.py        the exit-coded verdict gate
  traces/                recorded event streams
```

## Design notes

- **Correlation keys.** Card events carry `(game_id, position)`; attempt events
  carry only `attempt_id` (with `game_id` in the payload, not the bindings, so
  they route only to attempt entities); game events carry `game_id`.
- **`game.complete` is deliberately NOT a terminal event.** A terminal would
  settle rule 3's prohibition as *satisfied* at completion and blind it to
  anything that happens afterward (a false green). The game entity is reclaimed
  by the quiescence TTL instead, so the rule stays armed. Cheat "act after
  complete" proves post-completion activity is still caught.
- **Reorder grace < deadline.** The engine's `grace` (0.5s) is kept below the
  3-second `within` deadline; a larger window can leave a resolving event
  buffered when the live timer fires, reading a resolved attempt as a false
  timeout.
