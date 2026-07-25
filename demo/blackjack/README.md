# Blackjack, verified at runtime

A browser Blackjack game (player vs dealer, single deck) whose every move is
checked live by [behave-rv](https://github.com/moraneus/behave-rv). Standard
library only, plus `behave-rv`.

## Your table rules (the policies)

Each dealt hand is one monitored entity (correlation key `hand_id`). The four
rules you stated live in `monitoring/policies/`, verbatim, as Gherkin:

| # | Rule | Form | File |
|---|------|------|------|
| 1 | Once a hand stands, it is never dealt another card | scoped `never` | `01_no_card_after_stand.feature` |
| 2 | A hand that busts is never settled as a win | scoped `never` | `02_bust_never_wins.feature` |
| 3 | Every dealt hand reaches settlement within 30 seconds | `within` | `03_settlement_within_30s.feature` |
| 4 | A payout only ever happens after settlement | `before` | `04_payout_after_settlement.feature` |
| 5 | A hand settled as a loss is never paid out | scoped `never` | `05_losing_hand_not_paid.feature` |

## Run it

```bash
pip install "behave-rv>=0.3.1"          # Python 3.10+

# 1) Play in the browser, watch the monitor alongside
python app/server.py                    # game: http://127.0.0.1:8802
                                        # monitor: http://127.0.0.1:7102
#   ports are configurable: --game-port / --dash-port

# 2) Scripted demo, no browser - plays healthy hands + injected cheats
python demo.py                          # prints every verdict + explanation
python demo.py --dashboard              # also serve the live monitor to watch

# 3) The gates (what CI runs)
python -m behave_rv catalog diff --steps monitoring/steps.py \
  --catalog monitoring/catalog.json --policies monitoring/policies \
  --app app/blackjack.py --fail-on-app-risk --trace monitoring/traces/scripted.jsonl
python monitoring/replay_check.py
```

In the browser you play a fair game (Hit / Stand / New hand). Two clearly
labelled **cheat buttons** inject corrupted hands onto the event stream - a card
dealt after stand, and a busted hand settled as a win - so you can watch the
monitor flag them in real time. The dashboard shows every rule as a card with
per-hand verdicts (green satisfied / red violated), the failing step and
deciding events for each violation, the live event feed, and a stability strip
proving the running code still matches the committed contract.

## How it is wired

- `app/blackjack.py` - the game. At every transition it emits an `Event(...)`
  (`hand.dealt`, `hand.stood`, `hand.busted`, `hand.settled`, `hand.payout`,
  `hand.closed`). Instrumentation is additive; the game logic is untouched by it.
- `monitoring/steps.py` - the vocabulary the policies bind to (pure predicates).
- `monitoring/catalog.json` - the generated two-sided contract (committed).
- `monitoring/STEPS.md` - generated authoring reference for writing policies.
- `app/scenarios.py` - the shared scripted traffic (healthy hands + cheats).

`hand.closed` is the terminal event: it frees a hand's monitor state and settles
its open policies. Because it settles the two scoped prohibitions (rules 1 and 2)
as satisfied, those rules are armed only from their trigger until the hand
closes - a forbidden event arriving *after* close is not caught. The demo's two
"window probe" seeds inject exactly that and are (correctly) not flagged, to make
the detection window visible rather than a surprise.
