# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values -
use the exact strings listed under each step (a value the app never
emits will compile but silently never match).
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a game is "{status}"`

- **identity**: `game.status.is` (trigger)
- **observes**: event `game.status`, entity key `game_id`
- **parameters**: `status`
  - `status` values seen in the recorded trace: `over`, `started`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a game is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a game is "<status>"
    Then a game is "<status>" before

  Scenario: <your policy name>  # deadline
    When a game is "<status>"
    Then a game is "<status>" within "30" seconds

```

## `the snake moves`

- **identity**: `game.move.any` (trigger)
- **observes**: event `game.move`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the snake moves never happens

  Scenario: <your policy name>  # eventuality
    Then the snake moves has happened

  Scenario: <your policy name>  # precedence
    When the snake moves
    Then the snake moves before

  Scenario: <your policy name>  # deadline
    When the snake moves
    Then the snake moves within "30" seconds

```

## `the snake reverses into itself`

- **identity**: `game.move.reversal` (trigger)
- **observes**: event `game.move`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the snake reverses into itself never happens

  Scenario: <your policy name>  # eventuality
    Then the snake reverses into itself has happened

  Scenario: <your policy name>  # precedence
    When the snake reverses into itself
    Then the snake reverses into itself before

  Scenario: <your policy name>  # deadline
    When the snake reverses into itself
    Then the snake reverses into itself within "30" seconds

```

## `a point is scored`

- **identity**: `game.food.scored` (trigger)
- **observes**: event `game.food`, entity key `game_id`
- **also writable as**: `food is eaten`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a point is scored never happens

  Scenario: <your policy name>  # eventuality
    Then a point is scored has happened

  Scenario: <your policy name>  # precedence
    When a point is scored
    Then a point is scored before

  Scenario: <your policy name>  # deadline
    When a point is scored
    Then a point is scored within "30" seconds

```

## `the snake grows`

- **identity**: `game.grow.happens` (trigger)
- **observes**: event `game.grow`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the snake grows never happens

  Scenario: <your policy name>  # eventuality
    Then the snake grows has happened

  Scenario: <your policy name>  # precedence
    When the snake grows
    Then the snake grows before

  Scenario: <your policy name>  # deadline
    When the snake grows
    Then the snake grows within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
