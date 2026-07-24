# Tic-Tac-Toe with runtime verification built in

Two players at one keyboard (X and O click squares), with a behave-rv monitor
enforcing the laws of the game live, in your own words, against the game's real
event stream. Python standard library only, plus `behave-rv` (>= 0.3.0).

## The laws (your policies, in `monitoring/policies/`)

1. **Strict alternation** -- after X moves, the very next move must be O's, and
   vice versa; no player moves twice in a row.
2. **No move after finish** -- once a game is won or drawn, no further move may
   ever be made in it.
3. **Every game finishes** -- every game that starts is eventually won or
   drawn; none abandoned forever.
4. **No orphan moves** -- a move only happens after its game has started; a move
   from nowhere is stream corruption. (Promoted from a suggestion on your call.)

Each is one Gherkin scenario compiled into a per-game monitor. A violation is
reported as your own scenario replayed with the failing step marked and the
real events bound in.

## Run it

```bash
# 1) The browser game + live dashboard
python server.py                 # game at http://127.0.0.1:8804
                                 # monitor at http://127.0.0.1:7104
#    ports are configurable: --port 8804 --dashboard-port 7104

# 2) The scripted demo (no browser needed): 6 games, 4 with injected corruption
python demo.py                   # prints every verdict + explanation, records a trace
python demo.py --serve           # same, but streams live into the dashboard (:7104) and holds it open

# 3) The gates (what CI runs)
python -m behave_rv catalog diff --steps monitoring/steps.py \
    --catalog monitoring/catalog.json --policies monitoring/policies \
    --app app/game_service.py --fail-on-app-risk
python monitoring/replay_check.py     # exit 1 on unexpected verdicts
```

## The live view

`server.py` and `demo.py --serve` expose the behave-rv dashboard at
**http://127.0.0.1:7104**. There you see every law as a card with its
per-game verdicts (green satisfied / red violated), each violation rendered as
the authored scenario with the failing step marked and the deciding events
listed, the live event feed, and a stability strip that is green when the code
still matches the committed two-sided contract (step predicates *and* the app's
emit sites). The correct game keeps every card green; the injection buttons and
the scripted demo turn the matching card red.

Screenshots: `docs/screenshot-game.png`, `docs/screenshot-dashboard.png`.

## Seeing violations

The browser game is a *correct* implementation: it refuses out-of-turn,
occupied-cell, and post-finish moves, so honest play keeps the monitor green
(that green is the point -- it is evidence the game obeys its own laws). To see
the monitor *catch* a violation, corruption is injected as events, never as a
game bug:

- In the browser, the **"inject a corrupted event"** panel fires a double move
  (law 1), a move after the win (law 2), or a move for a game that never started
  (law 4) straight to the monitor.
- `demo.py` scripts six games: two healthy, then a double move, a move after
  the win, a game abandoned before finishing (law 3), and a move from nowhere
  (law 4) -- via `service.force_move`, which bypasses the game's guards to model
  a corrupted move on the wire.

## How the code is instrumented

`app/game_service.py` is the game logic. Its only coupling to monitoring is an
injected `emit` callback it calls at each observable change -- the logic is
never reshaped to be observed. It emits three event types, all keyed by
`game_id` (one monitor per game):

| Event | When | Payload |
|---|---|---|
| `game.status` | lifecycle | `state` in {started, won, draw} (won carries `winner`) |
| `game.move` | a stone placed | `player`, `cell`, `prev_player` |
| `game.ended` | a game leaves the board (**terminal**) | `outcome` in {won, draw, abandoned} |

`prev_player` (the player who moved immediately before, or `"none"`) is the one
modelling decision worth calling out: it is what lets strict alternation be a
single-event `never` predicate (`player == prev_player`), checked on *every*
move. The alternative -- the `previously` operator -- settles on the first move
alone and so cannot police a repeated property. `prev_player` is stamped from
the true move order in the emit layer, not by the turn logic, so a double move
however it arises is caught.

## Files

```
app/game_service.py          game logic + additive event emission
server.py                    browser game (:8804) + live dashboard (:7104)
demo.py                      scripted demo (batch, or --serve for the dashboard)
demo_script.py               the shared five-game script (healthy + injected faults)
monitoring/
  steps.py                   the vocabulary: build_registry() + load_policies()
  policies/                  the three laws (your policies)
  catalog.json               generated two-sided contract (committed)
  STEPS.md                   generated vocabulary doc (do not hand-edit)
  SUGGESTED_POLICIES.md      proposals for you to accept or reject
  generate_steps_doc.py      regenerates STEPS.md
  replay_check.py            the exit-coded verdict gate
  traces/                    recorded event streams (demo + live sessions)
```
