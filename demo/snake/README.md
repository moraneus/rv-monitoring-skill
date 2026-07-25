# Snake, born monitorable

A browser Snake game whose rules are watched at runtime by a
[behave-rv](https://github.com/moraneus/behave-rv) monitor, with a live
dashboard. Standard library only (plus `behave-rv`).

## Run it

```bash
# the browser game + live dashboard
python -m app.server                      # game on :8801, dashboard on :7101
#   python -m app.server --game-port 8801 --dash-port 7101

# the scripted demo (no browser): plays healthy + corrupted games,
# streams verdicts to the same dashboard, prints the explanations
python demo.py                            # dashboard on :7101

# the exit-coded gates
python monitoring/replay_check.py                          # verdict gate
python -m behave_rv catalog diff --steps monitoring/steps.py \
  --catalog monitoring/catalog.json --policies monitoring/policies \
  --app app/game.py app/traffic.py --fail-on-app-risk \
  --trace monitoring/traces/demo_session.jsonl             # stability gate
```

> **Maintainer note - the contract surface is TWO files.** The catalog is
> saved and diffed against **both** `app/game.py` (the game engine's emit site)
> **and** `app/traffic.py` (the scripted/corrupted emit site). Always pass both
> to `--app` (as the commands above do). Diffing against only one file drops the
> other side of the contract and will read as a phantom break - it is not a
> break, just an incomplete `--app` list. Same rule for `catalog save`.

Play with the arrow keys (or WASD). The **live dashboard** at
`http://127.0.0.1:7101` shows each of your policies as a card with its
per-entity verdicts, the rendered explanation for every violation, the live
event feed, and a green strip confirming the code still matches the committed
contract. Honest play never breaks a rule - the "See a violation live" buttons
on the game page inject a corrupted event into a throwaway game so you can watch
a policy card turn red.

## The three roles

* **The engine** (`app/game.py`) owns the game logic and emits an `Event(...)`
  at every transition. The browser is a thin client over it.
* **You** own the policies in `monitoring/policies/` - the three rules below,
  transcribed from the request. The monitor never grades itself.
* **behave-rv** owns the verdicts, deterministically, with no model in the
  runtime path.

## The monitored rules

| # | Rule | Policy file | Fragment form |
|---|------|-------------|---------------|
| 1 | Once a game is over, no further **moves** may be played | `01_no_moves_after_over.feature` | scoped `never` |
| 1 | Once a game is over, no further **points** may be scored | `02_no_points_after_over.feature` | scoped `never` |
| 2 | Every food eaten is followed by growth within 2 seconds | `03_food_then_grow.feature` | `within` |
| 3 | The snake never reverses straight into itself (180°) | `04_no_reversal.feature` | self-contained `never` |

Rule 3 reads the raw `direction`/`prev_direction` fields and computes the
reversal in the predicate, so a corrupted move can't hide a 180 behind a flag.

## One modeling decision (reversible)

A game entity has **no terminal event**. "Over" is deliberately *not* terminal:
a terminal would settle the two post-over prohibitions (rules 1a/1b) to a false
green the instant the game ends, and a move arriving after that would spawn a
fresh instance that never sees the scope open. Leaving "over" non-terminal keeps
those prohibitions armed, so a post-over move or point is actually caught.
The cost: entities are reclaimed by a quiescence TTL rather than at a terminal,
so the practical guarantee window for rules 1a/1b is that TTL (unbounded in the
live server; the demo/gate close the stream explicitly). The alternative -
declaring "over" terminal - was rejected for the false-green it produces.
```
