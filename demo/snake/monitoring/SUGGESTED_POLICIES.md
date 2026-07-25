# Suggested policies (proposals - you decide)

These are drafts *I* thought of. They are not active. Move any you want into
`monitoring/policies/` and re-run the gates; leave the rest here. Each below
compiles against the current vocabulary and produces zero violations on the
healthy scripted flows.

## 2026-07-25: growth must be earned

**Observes:** `game.grow`, `game.food` (key `game_id`)
**Why:** The snake should only ever grow as a result of eating. A growth with
no preceding point would mean length is being handed out for free - the mirror
image of rule 2 (which catches food that fails to grow).

```gherkin
Feature: growth is always earned

  Scenario: the snake only grows after scoring a point
    When the snake grows
    Then a point is scored before
```

Note: `before` is decided once, at the first growth, and settles. It proves
"growth was earned at least once", not "every growth was earned". A
per-growth version would need history stamping (stamp each `game.grow` with the
score at that moment and write a self-contained `never` over it) - say the word
and I will add the emission and the step.

## 2026-07-25: points come from play

**Observes:** `game.food`, `game.move` (key `game_id`)
**Why:** A point should only be scored during actual play, i.e. after the snake
has moved at least once. A score before any move suggests a phantom point
injected outside the game loop.

```gherkin
Feature: points come from play

  Scenario: a point is only scored after the snake has moved
    When a point is scored
    Then the snake moves before
```
