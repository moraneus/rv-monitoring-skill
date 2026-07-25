# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values -
use the exact strings listed under each step (a value the app never
emits will compile but silently never match).
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a game starts`

- **identity**: `game.lifecycle.started` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game starts never happens

  Scenario: <your policy name>  # eventuality
    Then a game starts has happened

  Scenario: <your policy name>  # precedence
    When a game starts
    Then a game starts before

  Scenario: <your policy name>  # deadline
    When a game starts
    Then a game starts within "30" seconds

```

## `a move is played`

- **identity**: `game.move.any` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a move is played never happens

  Scenario: <your policy name>  # eventuality
    Then a move is played has happened

  Scenario: <your policy name>  # precedence
    When a move is played
    Then a move is played before

  Scenario: <your policy name>  # deadline
    When a move is played
    Then a move is played within "30" seconds

```

## `a move is played by "{player}"`

- **identity**: `game.move.by` (trigger)
- **observes**: event `game.status`, entity key `game_id`
- **parameters**: `player`
  - `player` values seen in the recorded trace: `O`, `X`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a move is played by "<player>" never happens

  Scenario: <your policy name>  # eventuality
    Then a move is played by "<player>" has happened

  Scenario: <your policy name>  # precedence
    When a move is played by "<player>"
    Then a move is played by "<player>" before

  Scenario: <your policy name>  # deadline
    When a move is played by "<player>"
    Then a move is played by "<player>" within "30" seconds

```

## `the opening move is played by "{player}"`

- **identity**: `game.move.opening_by` (trigger)
- **observes**: event `game.status`, entity key `game_id`
- **parameters**: `player`
  - `player` values seen in the recorded trace: `O`, `X`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the opening move is played by "<player>" never happens

  Scenario: <your policy name>  # eventuality
    Then the opening move is played by "<player>" has happened

  Scenario: <your policy name>  # precedence
    When the opening move is played by "<player>"
    Then the opening move is played by "<player>" before

  Scenario: <your policy name>  # deadline
    When the opening move is played by "<player>"
    Then the opening move is played by "<player>" within "30" seconds

```

## `the same player moves twice in a row`

- **identity**: `game.move.repeat` (trigger)
- **observes**: event `game.status`, entity key `game_id`

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

## `a move is played after the game is decided`

- **identity**: `game.move.after_decided` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a move is played after the game is decided never happens

  Scenario: <your policy name>  # eventuality
    Then a move is played after the game is decided has happened

  Scenario: <your policy name>  # precedence
    When a move is played after the game is decided
    Then a move is played after the game is decided before

  Scenario: <your policy name>  # deadline
    When a move is played after the game is decided
    Then a move is played after the game is decided within "30" seconds

```

## `a game is decided`

- **identity**: `game.decided.any` (trigger)
- **observes**: event `game.status`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is decided never happens

  Scenario: <your policy name>  # eventuality
    Then a game is decided has happened

  Scenario: <your policy name>  # precedence
    When a game is decided
    Then a game is decided before

  Scenario: <your policy name>  # deadline
    When a game is decided
    Then a game is decided within "30" seconds

```

## `a game is "{status}"`

- **identity**: `game.status.is` (trigger)
- **observes**: event `game.status`, entity key `game_id`
- **parameters**: `status`
  - `status` values seen in the recorded trace: `drawn`, `move`, `started`, `won`

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

## `a game is over`

- **identity**: `game.over.any` (trigger)
- **observes**: event `game.over`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game is over never happens

  Scenario: <your policy name>  # eventuality
    Then a game is over has happened

  Scenario: <your policy name>  # precedence
    When a game is over
    Then a game is over before

  Scenario: <your policy name>  # deadline
    When a game is over
    Then a game is over within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
