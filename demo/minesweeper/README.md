# Minesweeper with runtime verification

An 8x8, 10-mine Minesweeper you play in the browser, watched live by a
[behave-rv](https://github.com/moraneus/behave-rv) monitor. The game is
*monitorable by construction*: every state change emits an event, and three
human-owned policies are evaluated against that event stream by a
deterministic engine - no model, heuristic, or randomness in the verdict path.

## The rules being enforced

They live in `monitoring/policies/` as Gherkin (the policy id is the scenario
name), compiled into per-entity monitors:

1. **`01_no_reveal_after_boom`** - once a mine explodes, no cell may ever be
   revealed in that game. *(scoped prohibition, key `game_id`)*
2. **`02_no_double_reveal`** - a cell that has been revealed must never be
   revealed again, each cell of each game individually. *(scoped prohibition,
   key `(game_id, cell)`)*
3. **`03_flags_never_exceed_mines`** - the flag count must never exceed the
   board's mine count. *(prohibition over a payload predicate, key `game_id`)*
4. **`04_reveal_only_after_start`** - a cell is only revealed after the game
   has started; a reveal with no preceding `game.started` (a correlation-key or
   ordering bug) is a violation. *(precedence `before`, key `game_id`)*

The full authoring vocabulary is generated in `monitoring/STEPS.md`.

## Run it in the browser (live dashboard alongside)

```bash
python app/server.py                       # defaults: game 8803, dashboard 7103
python app/server.py --game-port 8803 --dash-port 7103
```

Open <http://127.0.0.1:8803>. Left-click reveals, right-click flags. The
behave-rv dashboard is embedded on the right (also at
<http://127.0.0.1:7103>): each policy is a card with its per-game verdicts,
the live event feed, and a stability strip showing the code still matches the
committed contract. When a policy is violated you see the authored scenario
replayed with the failing step marked and the deciding events attached.

Honest play keeps every policy green. To see the monitor catch a violation,
use the three **"inject a corrupted event"** buttons - they push a raw event
onto the monitor's stream, bypassing every in-game guard (what a compromised
or out-of-band component would do). Verdicts settle within about a second.

## Run the scripted demo (no browser)

```bash
python demo.py                 # plays boards, records a trace, replays, reports
python demo.py --dashboard     # also opens the live dashboard and pauses on it
```

It plays one clean board, then three cheating boards - a reveal after the
boom, a double reveal of the same cell, and an 11th flag - injected as
corrupted events. It records the run to `monitoring/traces/demo_session.jsonl`
and re-runs it through a fresh engine (the "replay gate"), printing each
violation with its explanation. Exit code is non-zero unless exactly the three
expected violations are caught.

## The verification gates (CI)

```bash
# 1. two-sided stability contract: step predicates vs app emit sites
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/minesweeper.py \
  --fail-on-app-risk --trace monitoring/traces/demo_session.jsonl

# 2. deterministic replay of scripted traffic, pinned verdict counts
python monitoring/replay_check.py
```

Both exit 0 today. `catalog diff` reports a break if a code change moves what a
step matches or what an emit site emits; `replay_check.py` pins the healthy
flows at zero violations and the three faults at exactly one each.

## Layout

```
app/
  minesweeper.py   # the game engine + additive instrumentation (the monitored surface)
  server.py        # stdlib http.server UI + live monitor wiring + cheat injection
demo.py            # scripted play + cheats, records a trace, runs the replay gate
monitoring/
  steps.py         # the step vocabulary (5 predicates); build_registry() + load_policies()
  policies/        # the three user-owned .feature rules
  catalog.json     # generated two-sided contract (committed)
  STEPS.md         # generated authoring surface
  SUGGESTED_POLICIES.md
  generate_steps_doc.py
  replay_check.py
  traces/          # recorded event streams
```

## How the encoding works (two notes worth knowing)

- **"At most once" (rule 2)** is expressed with two event types: a reveal
  *action* (`cell.reveal`) and the resulting revealed *state*
  (`cell.revealed`), emitted strictly after. The scope opens on the state, so
  a *first* reveal is legal and only a *second* reveal of an already-revealed
  cell violates. A plain `never` on the reveal would (correctly, by the
  operator's semantics) fire on the very first reveal.
- **No terminal event.** `game.over` is emitted but is deliberately *not*
  declared terminal: a terminal settles prohibitions as *satisfied* and frees
  the entity, which would blind rule 1 to exactly the post-boom reveals it
  exists to catch. Entities are reclaimed by the engine's quiescence TTL
  instead. The trade-off: `game_id` entities live until the TTL rather than
  ending crisply at game over.
