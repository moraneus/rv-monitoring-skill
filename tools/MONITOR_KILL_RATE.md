# Monitor kill rate: coverage confidence, quantified

The stability contract and `catalog coverage` tell you *statically* what the
monitor watches. This tool measures it *dynamically*: mutation testing where the
application is the subject and the monitor is the test suite. It mutates each
demo's app code one edit at a time and, for every mutant, runs the demo's own
runtime gate (`monitoring/replay_check.py`). A mutant is **killed** if the gate
goes red. The kill rate is how much of the app's behaviour the monitor actually
catches; the survivors are the mutations it is blind to.

Run it:

```
uv run --no-project --with behave-rv==0.5.0 python tools/run_kill_rates.py
```

## Results (behave-rv 0.5.0, the ten demos)

| Demo | Kind | Mutants | Killed | Runtime kill rate |
|---|---|---:|---:|---:|
| lending | service | 8 | 7 | 87.5% |
| devices | service | 23 | 16 | 69.6% |
| bookings | service | 22 | 13 | 59.1% |
| payments | service | 42 | 20 | 47.6% |
| parcels | service | 34 | 16 | 47.1% |
| tictactoe | game | 100 | 36 | 36.0% |
| blackjack | game | 130 | 44 | 33.8% |
| minesweeper | game | 97 | 30 | 30.9% |
| snake | game | 138 | 38 | 27.5% |
| memory | game | 78 | 20 | 25.6% |

**Mean runtime kill rate: 46.5%.**

## What the numbers mean

A kill rate well below 100% is expected and correct, not a failure. Much of an
application's code is internal computation (a card total, a board coordinate)
that no policy needs to watch - mutating it survives because it never changes an
observable, monitored behaviour. The metric's value is comparative and
diagnostic:

- **Services score higher than games** (services 47-88%, games 26-36%). A
  service's policies track its state transitions fairly completely; a game has
  far more internal logic than its handful of rules ("no move after game over")
  care about.
- **A low score points at coverage gaps.** Run `catalog coverage` on the same
  demo and the survivors line up with the unwatched surface. On memory (25.6%,
  the lowest), coverage names three unwatched events (`match.found`,
  `game.started`, `game.completed`) and thirteen unwatched fields, including
  behavioural ones like `card.flipped.already_matched` - a real gap, not noise.

## The closed loop

The three tools compose into a coverage-confidence workflow:

1. **`catalog coverage`** (static) names the emitted surface no policy watches.
2. **kill rate** (dynamic) quantifies how much the monitor actually catches and
   ranks demos by exposure.
3. Where a low kill rate and an unwatched surface coincide on a *behavioural*
   field or event, that is a suggestion for `SUGGESTED_POLICIES.md`. For memory,
   the loop yields concrete proposals (watch `match.found`; assert a matched
   card is never re-flipped via `card.flipped.already_matched`) - recorded there.

A high kill rate is not a guarantee of a correct specification, and a low one is
not automatically a defect; the tool turns "are we checking the right things?"
from a hope into a number you can watch move.
