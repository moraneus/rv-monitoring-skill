# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a card is flipped`

- **identity**: `card.flip.is` (trigger)
- **observes**: event `card.flip`, entity key `game_id, position`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a card is flipped never happens

  Scenario: <your policy name>  # eventuality
    Then a card is flipped has happened

  Scenario: <your policy name>  # precedence
    When a card is flipped
    Then a card is flipped before

  Scenario: <your policy name>  # deadline
    When a card is flipped
    Then a card is flipped within "30" seconds

```

## `a card is matched`

- **identity**: `card.matched.is` (trigger)
- **observes**: event `card.matched`, entity key `game_id, position`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a card is matched never happens

  Scenario: <your policy name>  # eventuality
    Then a card is matched has happened

  Scenario: <your policy name>  # precedence
    When a card is matched
    Then a card is matched before

  Scenario: <your policy name>  # deadline
    When a card is matched
    Then a card is matched within "30" seconds

```

## `an attempt is ready`

- **identity**: `attempt.pending.is` (trigger)
- **observes**: event `attempt.pending`, entity key `attempt_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then an attempt is ready never happens

  Scenario: <your policy name>  # eventuality
    Then an attempt is ready has happened

  Scenario: <your policy name>  # precedence
    When an attempt is ready
    Then an attempt is ready before

  Scenario: <your policy name>  # deadline
    When an attempt is ready
    Then an attempt is ready within "30" seconds

```

## `an attempt is resolved`

- **identity**: `attempt.resolved.is` (trigger)
- **observes**: event `attempt.resolved`, entity key `attempt_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then an attempt is resolved never happens

  Scenario: <your policy name>  # eventuality
    Then an attempt is resolved has happened

  Scenario: <your policy name>  # precedence
    When an attempt is resolved
    Then an attempt is resolved before

  Scenario: <your policy name>  # deadline
    When an attempt is resolved
    Then an attempt is resolved within "30" seconds

```

## `an attempt is resolved as "{outcome}"`

- **identity**: `attempt.resolved.outcome` (trigger)
- **observes**: event `attempt.resolved`, entity key `attempt_id`
- **parameters**: `outcome`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then an attempt is resolved as "<outcome>" never happens

  Scenario: <your policy name>  # eventuality
    Then an attempt is resolved as "<outcome>" has happened

  Scenario: <your policy name>  # precedence
    When an attempt is resolved as "<outcome>"
    Then an attempt is resolved as "<outcome>" before

  Scenario: <your policy name>  # deadline
    When an attempt is resolved as "<outcome>"
    Then an attempt is resolved as "<outcome>" within "30" seconds

```

## `the game starts`

- **identity**: `game.start.is` (trigger)
- **observes**: event `game.start`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the game starts never happens

  Scenario: <your policy name>  # eventuality
    Then the game starts has happened

  Scenario: <your policy name>  # precedence
    When the game starts
    Then the game starts before

  Scenario: <your policy name>  # deadline
    When the game starts
    Then the game starts within "30" seconds

```

## `the game is complete`

- **identity**: `game.complete.is` (trigger)
- **observes**: event `game.complete`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the game is complete never happens

  Scenario: <your policy name>  # eventuality
    Then the game is complete has happened

  Scenario: <your policy name>  # precedence
    When the game is complete
    Then the game is complete before

  Scenario: <your policy name>  # deadline
    When the game is complete
    Then the game is complete within "30" seconds

```

## `a game action occurs`

- **identity**: `game.action.is` (trigger)
- **observes**: event `game.action`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a game action occurs never happens

  Scenario: <your policy name>  # eventuality
    Then a game action occurs has happened

  Scenario: <your policy name>  # precedence
    When a game action occurs
    Then a game action occurs before

  Scenario: <your policy name>  # deadline
    When a game action occurs
    Then a game action occurs within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
