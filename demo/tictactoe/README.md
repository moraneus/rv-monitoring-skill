# Tic-Tac-Toe, born monitorable

A browser tic-tac-toe for two players at one keyboard, with a live
[behave-rv](https://github.com/moraneus/behave-rv) runtime monitor alongside
that enforces the laws of the game as they are played. Python standard
library only, plus `behave-rv`.

## The three laws (owned by the user, in `monitoring/policies/`)

1. **Strict alternation** - immediately after X moves, the next move must be
   O's, and vice versa. (`01_strict_alternation.feature`)
2. **No play after decision** - once a game is won or drawn, no further move
   may be made in it. (`02_no_move_after_decided.feature`)
3. **Every game finishes** - every game that starts must eventually be won or
   drawn; none abandoned forever. (`03_every_game_finishes.feature`)

The engine owns the verdicts; no model or randomness is in the runtime path.

## Run it

Both ports are configurable (`--game-port`, `--dash-port`).

```bash
pip install "behave-rv>=0.3.1"          # Python 3.10+

# interactive browser game + live dashboard
python app/server.py                    # game http://127.0.0.1:8804
                                        # monitor http://127.0.0.1:7104

# scripted demo, no browser: plays 5 games (2 clean, 3 with injected
# corrupted events) into the live dashboard, then prints the verdicts
python demo.py                          # dashboard http://127.0.0.1:7104
python demo.py --linger 0               # play, print verdicts, exit
```

Open `http://127.0.0.1:8804` and play. The dashboard is embedded on the right
of the game page (and standalone at `http://127.0.0.1:7104`): each law is a
card with per-game verdicts, every violation is explained by replaying your
own scenario with the failing step marked, and a green strip confirms the
code still matches the committed contract on both sides.

**See a violation live in the browser:** start a game, make a move, then
click *New game* before it finishes - law 3 flags the abandoned game red
while the rest stay green.

## The verification gate

```bash
# is the code still consistent with the committed contract? (CI gate)
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/game.py \
  --fail-on-app-risk --trace monitoring/traces/scripted.jsonl

# do the policies still produce the pinned verdicts over scripted traffic?
python monitoring/replay_check.py       # 21 verdicts, 3 violations, exit 0
```

`monitoring/replay_check.py` drives healthy games plus the three corrupted
faults (a double move, a move injected after the win through the real
`game.over` terminal, and an abandoned game) and pins the verdict counts.
CI wiring is in `monitoring/ci-snippet.yml`.

## How it is wired

The game code emits events beside its logic - never reshaped to be observed:

* `game.status` - one type for the tracked states `started` / `move` / `won`
  / `drawn`, keyed by `game_id`. Move events also carry `player`, `cell`,
  `move_number`, and two history-stamped fields: `prev_player` (the previous
  mover, from the true move order) and `after_finish` (`"yes"` only if the
  board was already decided).
* `game.over` - the separate terminal, `outcome` = `won` / `drawn` /
  `abandoned`. It settles every open policy on the game and frees its state.

Laws 1 and 2 are self-contained `never` prohibitions over the stamped
fields, so they are checked at *every* move and a corrupted event is caught
even after the game's terminal. Law 3 is an eventuality (`has happened`)
that the `game.over` "abandoned" terminal turns into a violation. The
generated `monitoring/STEPS.md` is the policy-authoring vocabulary;
`monitoring/SUGGESTED_POLICIES.md` holds further proposals.
