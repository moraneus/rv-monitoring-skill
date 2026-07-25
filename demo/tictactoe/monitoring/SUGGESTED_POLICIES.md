# Suggested policies

Proposals only. You own the policies: nothing here is active until you move
it into `monitoring/policies/`. Each entry below compiles against the current
vocabulary and produces zero violations on healthy play.

## 2026-07-25: moves may not precede the game start

**Observes:** `game.status` (statuses `move`, `started`), key `game_id`
**Why:** a corrupted or misordered producer could emit a move for a
`game_id` that never started. This precedence check catches a move that has
no `started` in its past. (Triggered `before` arms at the first move and
settles - "the first move came after start" implies every move did.)

```gherkin
Feature: moves come after the game starts

  Scenario: no move may be played before the game has started
    When a move is played
    Then a game starts before
```

## 2026-07-25: X always makes the opening move

**Observes:** `game.status` (status `move`, fields `move_number`, `player`),
key `game_id`
**Why:** the game seats X first by convention, but nothing asserts it. This
flags any game whose first move (`move_number == "1"`) is O - a seating or
turn-init bug, or a corrupted opening event. Uses the new
`the opening move is played by "{player}"` step (added this change; reads
fields already emitted, no new instrumentation).

```gherkin
Feature: opening convention

  Scenario: X always makes the opening move
    Then the opening move is played by "O" never happens
```

## Out of fragment (noted, not proposed)

- **"a game is decided at most once"** - a counting property. The tempting
  `Given a game is decided / Then a game is decided never happens`
  transcription misfires: the scope opens on the first decision and that
  same event matches the prohibition, so every legitimate first win/draw
  would violate. A sound in-fragment version needs an app-side re-decision
  marker event with a self-contained `never` on it. Raise it if you want it.
- **"X and O each make a fair share of games' opening moves"** - an
  aggregate across games. Out of the single-entity fragment entirely.
