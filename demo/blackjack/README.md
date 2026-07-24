# Blackjack, born monitorable

Browser Blackjack (player vs dealer, one deck) with runtime verification built
in via [behave-rv](https://github.com/moraneus/behave-rv). The monitored entity
is a **hand** (one round), keyed by `hand_id`. The game emits events as it runs;
behave-rv compiles your four table rules into per-hand monitors and shows
verdicts live on its dashboard.

## Run it live (browser + dashboard)

```bash
python run_live.py            # game :8802, dashboard :7102 (both configurable)
python run_live.py --game-port 8802 --dash-port 7102
```

- **Game table:** http://127.0.0.1:8802 - deal with *New hand*, then *Hit* /
  *Stand*.
- **RV dashboard:** http://127.0.0.1:7102 - each of your four rules is a card
  with its per-hand verdicts, a rendered explanation for any violation, the live
  event feed, and a stability strip showing the code still matches the committed
  contract (`catalog.json`), on both the step side and the app's emit sites.

Every action pushes real events (`hand.dealt`, `hand.card`, `hand.stand`,
`hand.bust`, `hand.settled`, `hand.payout`, `hand.closed`) through the engine.
A service-relative clock keeps the `within` deadline firing on wall time for a
quiet table.

## Scripted demo (no browser needed)

Plays honest hands, then injects four corrupted event sequences - one per rule,
including the two you named (a card dealt after a stand, and a busted hand
settled as a win):

```bash
python demo.py                 # narrate + drive the dashboard, stays up (Ctrl-C)
python demo.py --no-dashboard  # headless: print every verdict + explanation
```

## The rules (yours, in monitoring/policies/)

| # | Rule | Form | File |
|---|------|------|------|
| 1 | Once a hand stands, never dealt another card | scoped `never` | `01_stand_locks_hand.feature` |
| 2 | A busted hand is never settled as a win | scoped `never` | `02_bust_cannot_win.feature` |
| 3 | Every dealt hand settles within 30 seconds | `within` | `03_settles_within_30s.feature` |
| 4 | A payout only happens after settlement | `before` | `04_payout_after_settlement.feature` |
| 5 | A hand is never settled twice | `never` | `05_no_double_settlement.feature` |

Rules 1 and 2 are scoped to the player: after the player stands the dealer still
draws (those cards go to the *dealer*, which is legal), and a *dealer* bust that
wins is legal - so both rules watch the player's side only.

Rule 5 catches a double settlement via a `hand.resettled` marker: the game's
settle path emits it if invoked on an already-settled hand (honest play never
does). "Settle at most once" is a counting property outside the temporal
fragment, so it is watched through this marker rather than by counting
`hand.settled` events; a raw stream-duplicate of `hand.settled` that never
passes the guard is out of reach.

## The verification gates

```bash
# static two-sided contract check (step predicates + app emit sites)
python -m behave_rv catalog diff --steps monitoring/steps.py \
  --catalog monitoring/catalog.json --policies monitoring/policies \
  --app app/game.py --fail-on-app-risk \
  --trace monitoring/traces/representative.jsonl

# deterministic replay gate: healthy hands (0 violations) + 4 injected cheats
python monitoring/replay_check.py     # exit 0 when the 4 cheats fire, nothing else
```

## Layout

```
app/game.py          # the game + all Event(...) emission sites
app/server.py        # stdlib http.server UI (inline HTML/JS, no CDNs)
run_live.py          # live entry point: game + dashboard + engine
demo.py              # scripted cheating demo
monitoring/
  steps.py           # the vocabulary (build_registry / load_policies)
  policies/          # your four rules, one Feature per file
  catalog.json       # generated two-sided contract
  STEPS.md           # generated authoring surface
  SUGGESTED_POLICIES.md
  replay_check.py    # exit-coded verdict gate
  traces/            # recorded streams for liveness checks
```
