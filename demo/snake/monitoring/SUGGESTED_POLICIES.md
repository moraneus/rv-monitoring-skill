# Suggested policies (proposals - you decide)

These are drafts *I* thought of from the monitorable surface. They are NOT
active. Move any you want into `monitoring/policies/` yourself, then rerun the
gates. Each compiles against the current registry.

Your requested rules are live in `monitoring/policies/`:
`01_no_activity_after_game_over.feature` (rule 1, split into two scenarios -
moves and points - because a policy has one obligation each),
`02_food_growth_within_2s.feature` (rule 2),
`03_no_reversal_accepted.feature` (rule 3), and
`04_start_precedes_activity.feature` (promoted 2026-07-25 from the suggestion
below; you extended its intent to cover scoring as well as moving, so it went
in as two `before` scenarios).

---

## 2026-07-25: every point scored comes from eating food

**Observes:** `game.score`, `snake.food` / key `game_id`
**Why:** score should only ever move at a food event. A `game.score` whose
immediate predecessor is not a food event means points appeared from somewhere
other than eating - the exact shape of the injected `zombie` corruption.

```gherkin
Feature: points are earned only by eating

  Scenario: a score is immediately preceded by eating food
    When points are scored
    Then the snake eats food previously
```

## 2026-07-25: a game that starts eventually ends

**Observes:** `game.status` (started / over) / key `game_id`
**Why:** surfaces games that never reach `over` - a snake stuck in a tick loop
that never dies. NOTE: this needs a terminal event to ever produce a
*violated* verdict; with `game.over` deliberately non-terminal (see the report)
it stays `pending` until the game ends and only ever reads satisfied. Offered
mainly to make the "no terminal" trade-off concrete - accept only if you also
want to add a terminal event, which would re-open the rule-1 false-green risk.

```gherkin
Feature: games terminate

  Scenario: a started game eventually ends
    Then a game is "over" has happened
```
