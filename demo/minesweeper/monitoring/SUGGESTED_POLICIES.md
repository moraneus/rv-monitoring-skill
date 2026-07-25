# Suggested policies (proposals - you decide what becomes a policy)

These are agent proposals over the existing event vocabulary. None is active;
move one into `monitoring/policies/` yourself if you want it enforced.

## 2026-07-25: a board only detonates on a real reveal

**Observes:** `mine.boom` (`board.mine.boom`), `board.reveal` (`board.reveal.any`)
**Why:** the current rules police what happens AFTER a boom. This is the mirror
image: a `mine.boom` should never arrive on a board where nothing was ever
revealed - it would mean an explosion fabricated out of nothing. Catches a
corrupted stream that injects a boom with no reveal behind it.

```gherkin
Feature: an explosion has a cause

  Scenario: a mine only explodes after some cell was revealed
    When a mine explodes
    Then a cell is revealed on the board before
```

## 2026-07-25: a square is seen only after it is revealed

**Observes:** `cell.seen` (`cell.seen.state`), `cell.reveal` (`cell.reveal.occurs`)
**Why:** the `cell.seen` state latch is what rule 2 (no double reveal) leans on.
This proposal guards the latch itself: `cell.seen` must be preceded by the
`cell.reveal` it records, so a stream cannot open the "already revealed" scope
for a square that was never actually revealed.

```gherkin
Feature: the seen-latch is honest

  Scenario: a cell is marked seen only after it was revealed
    When that cell was already revealed
    Then a cell is revealed before
```

Note: both proposals use the triggered `before` form, which arms ONCE per
entity and decides at the first trigger - exactly right here (the first boom /
first seen-latch is the one that must have a cause). They do not replace the
three committed prohibitions; they add a second, causal angle on the same
events.
