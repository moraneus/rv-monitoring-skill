# Suggested policies (proposals - you decide)

These are ideas I (the agent) thought of. Nothing here is active. Move a
scenario into `monitoring/policies/` yourself if you want it enforced, and
tell me - I will add any new step/event surface it needs, regenerate the
catalog for that intended change, and rerun the gates.

Your three requested rules already live in `monitoring/policies/`:
`01_no_reveal_after_boom`, `02_no_double_reveal`, `03_flags_never_exceed_mines`.

Each proposal below needs a small amount of NEW instrumentation or vocabulary
(named per item), so it does not compile against today's registry yet - that
is exactly why it is a proposal and not a policy. I did not add that surface,
to keep the build focused on the three rules you asked for.

---

## 2026-07-25: a cell is never flagged after it has been revealed

**Observes:** `cell.revealed` (state), a NEW `flag.placed` step keyed on the
cell. **Requires:** `flag.placed` to carry `cell` in its *bindings* (today it
carries the cell only in the payload) plus a `(game_id, cell)`-keyed flag step.
**Why:** flagging a cell you already uncovered is a UI/state bug; the monitor
would catch it per cell.

```gherkin
Feature: flags land only on hidden cells

  Scenario: no cell is flagged after it has been revealed
    Given the same cell has been revealed
    Then that cell is flagged never happens
```

## 2026-07-25: nothing happens before the game starts - PROMOTED

You promoted this on 2026-07-25. It now lives in
`monitoring/policies/04_reveal_only_after_start.feature`, backed by the new
`the game has started` step (observing the already-emitted `game.started`), the
catalog was regenerated for that intended change, and the replay traffic
exercises it including its fault (`g_no_start`). Kept here only as a record of
the promotion.

## 2026-07-25: no reveal after a win either

**Observes:** a NEW `game.won` event, `cell.reveal`. **Requires:** splitting
today's `game.over{result}` into (or adding) a distinct `game.won` event so a
win can open a scope; the current predicate cannot read the `result` payload
field in a scope step cleanly. **Why:** rule 1 covers reveals after a *loss*
(mine explodes); the symmetric case - reveals after a *win* - is currently
uncovered. Keyed on `game_id`.

```gherkin
Feature: a won game is also finished

  Scenario: no cell is revealed after the game is won
    Given the game is won
    Then a cell is revealed never happens
```

## 2026-07-25: a flagged cell is not revealed until it is unflagged

**Observes:** NEW per-cell `flag.placed` / `flag.removed` steps, `cell.reveal`.
**Requires:** `flag.placed` and `flag.removed` keyed on `(game_id, cell)`.
**Why:** the honest game blocks revealing a flagged cell; this interval-scope
rule makes that guard observable, and a corrupted reveal of a flagged cell
would be caught.

```gherkin
Feature: flags protect a cell from reveal

  Scenario: a flagged cell is not revealed while flagged
    Given the same cell is flagged until it is unflagged
    Then that cell is revealed never happens
```
