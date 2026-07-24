# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a move is made`

- **identity**: `game.move.any` (trigger)
- **observes**: event `game.move`, entity key `game_id`

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

## `a move is made by "{player}"`

- **identity**: `game.move.byplayer` (trigger)
- **observes**: event `game.move`, entity key `game_id`
- **parameters**: `player`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a move is made by "<player>" never happens

  Scenario: <your policy name>  # eventuality
    Then a move is made by "<player>" has happened

  Scenario: <your policy name>  # precedence
    When a move is made by "<player>"
    Then a move is made by "<player>" before

  Scenario: <your policy name>  # deadline
    When a move is made by "<player>"
    Then a move is made by "<player>" within "30" seconds

```

## `the same player moves twice in a row`

- **identity**: `game.move.repeat` (obligation)
- **observes**: event `game.move`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the same player moves twice in a row never happens

  Scenario: <your policy name>  # eventuality
    Then the same player moves twice in a row has happened

  Scenario: <your policy name>  # precedence
    When the same player moves twice in a row
    Then the same player moves twice in a row before

  Scenario: <your policy name>  # deadline
    When the same player moves twice in a row
    Then the same player moves twice in a row within "30" seconds

```

## `a game is finished`

- **identity**: `game.status.finished` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is finished never happens

  Scenario: <your policy name>  # eventuality
    Then a game is finished has happened

  Scenario: <your policy name>  # precedence
    When a game is finished
    Then a game is finished before

  Scenario: <your policy name>  # deadline
    When a game is finished
    Then a game is finished within "30" seconds

```

## `a game is started`

- **identity**: `game.status.started` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is started never happens

  Scenario: <your policy name>  # eventuality
    Then a game is started has happened

  Scenario: <your policy name>  # precedence
    When a game is started
    Then a game is started before

  Scenario: <your policy name>  # deadline
    When a game is started
    Then a game is started within "30" seconds

```

## `a game is won`

- **identity**: `game.status.won` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is won never happens

  Scenario: <your policy name>  # eventuality
    Then a game is won has happened

  Scenario: <your policy name>  # precedence
    When a game is won
    Then a game is won before

  Scenario: <your policy name>  # deadline
    When a game is won
    Then a game is won within "30" seconds

```

## `a game is won by "{player}"`

- **identity**: `game.status.wonby` (trigger)
- **observes**: event `game.status`, entity key `game_id`
- **parameters**: `player`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is won by "<player>" never happens

  Scenario: <your policy name>  # eventuality
    Then a game is won by "<player>" has happened

  Scenario: <your policy name>  # precedence
    When a game is won by "<player>"
    Then a game is won by "<player>" before

  Scenario: <your policy name>  # deadline
    When a game is won by "<player>"
    Then a game is won by "<player>" within "30" seconds

```

## `a game is a draw`

- **identity**: `game.status.draw` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is a draw never happens

  Scenario: <your policy name>  # eventuality
    Then a game is a draw has happened

  Scenario: <your policy name>  # precedence
    When a game is a draw
    Then a game is a draw before

  Scenario: <your policy name>  # deadline
    When a game is a draw
    Then a game is a draw within "30" seconds

```

## `a game ends as "{outcome}"`

- **identity**: `game.ended.outcome` (trigger)
- **observes**: event `game.ended`, entity key `game_id`
- **parameters**: `outcome`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game ends as "<outcome>" never happens

  Scenario: <your policy name>  # eventuality
    Then a game ends as "<outcome>" has happened

  Scenario: <your policy name>  # precedence
    When a game ends as "<outcome>"
    Then a game ends as "<outcome>" before

  Scenario: <your policy name>  # deadline
    When a game ends as "<outcome>"
    Then a game ends as "<outcome>" within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
