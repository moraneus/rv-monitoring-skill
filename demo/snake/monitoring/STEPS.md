# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a game is "{status}"`

- **identity**: `game.status.is` (trigger)
- **observes**: event `game.status`, entity key `game_id`
- **parameters**: `status`

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

## `a move is made`

- **identity**: `snake.move.made` (trigger)
- **observes**: event `snake.move`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a move is made never happens

  Scenario: <your policy name>  # eventuality
    Then a move is made has happened

  Scenario: <your policy name>  # precedence
    When a move is made
    Then a move is made before

  Scenario: <your policy name>  # deadline
    When a move is made
    Then a move is made within "30" seconds

```

## `a reversal is accepted`

- **identity**: `snake.move.reversal` (trigger)
- **observes**: event `snake.move`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a reversal is accepted never happens

  Scenario: <your policy name>  # eventuality
    Then a reversal is accepted has happened

  Scenario: <your policy name>  # precedence
    When a reversal is accepted
    Then a reversal is accepted before

  Scenario: <your policy name>  # deadline
    When a reversal is accepted
    Then a reversal is accepted within "30" seconds

```

## `the snake eats food`

- **identity**: `snake.food.eaten` (trigger)
- **observes**: event `snake.food`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the snake eats food never happens

  Scenario: <your policy name>  # eventuality
    Then the snake eats food has happened

  Scenario: <your policy name>  # precedence
    When the snake eats food
    Then the snake eats food before

  Scenario: <your policy name>  # deadline
    When the snake eats food
    Then the snake eats food within "30" seconds

```

## `the snake grows`

- **identity**: `snake.grow.happened` (trigger)
- **observes**: event `snake.grow`, entity key `game_id`

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

## `points are scored`

- **identity**: `game.score.made` (trigger)
- **observes**: event `game.score`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then points are scored never happens

  Scenario: <your policy name>  # eventuality
    Then points are scored has happened

  Scenario: <your policy name>  # precedence
    When points are scored
    Then points are scored before

  Scenario: <your policy name>  # deadline
    When points are scored
    Then points are scored within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
