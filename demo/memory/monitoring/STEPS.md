# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a matched card is flipped again`

- **identity**: `card.flipped.rematch` (trigger)
- **observes**: event `card.flipped`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a matched card is flipped again never happens

  Scenario: <your policy name>  # eventuality
    Then a matched card is flipped again has happened

  Scenario: <your policy name>  # precedence
    When a matched card is flipped again
    Then a matched card is flipped again before

  Scenario: <your policy name>  # deadline
    When a matched card is flipped again
    Then a matched card is flipped again within "30" seconds

```

## `the second card of an attempt is flipped`

- **identity**: `card.flipped.second` (trigger)
- **observes**: event `card.flipped`, entity key `game_id, attempt_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the second card of an attempt is flipped never happens

  Scenario: <your policy name>  # eventuality
    Then the second card of an attempt is flipped has happened

  Scenario: <your policy name>  # precedence
    When the second card of an attempt is flipped
    Then the second card of an attempt is flipped before

  Scenario: <your policy name>  # deadline
    When the second card of an attempt is flipped
    Then the second card of an attempt is flipped within "30" seconds

```

## `the attempt resolves`

- **identity**: `attempt.resolved.any` (trigger)
- **observes**: event `attempt.resolved`, entity key `game_id, attempt_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the attempt resolves never happens

  Scenario: <your policy name>  # eventuality
    Then the attempt resolves has happened

  Scenario: <your policy name>  # precedence
    When the attempt resolves
    Then the attempt resolves before

  Scenario: <your policy name>  # deadline
    When the attempt resolves
    Then the attempt resolves within "30" seconds

```

## `the attempt resolves as "{outcome}"`

- **identity**: `attempt.resolved.outcome` (trigger)
- **observes**: event `attempt.resolved`, entity key `game_id, attempt_id`
- **parameters**: `outcome`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the attempt resolves as "<outcome>" never happens

  Scenario: <your policy name>  # eventuality
    Then the attempt resolves as "<outcome>" has happened

  Scenario: <your policy name>  # precedence
    When the attempt resolves as "<outcome>"
    Then the attempt resolves as "<outcome>" before

  Scenario: <your policy name>  # deadline
    When the attempt resolves as "<outcome>"
    Then the attempt resolves as "<outcome>" within "30" seconds

```

## `a card is flipped after the game is over`

- **identity**: `card.flipped.postgame` (trigger)
- **observes**: event `card.flipped`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a card is flipped after the game is over never happens

  Scenario: <your policy name>  # eventuality
    Then a card is flipped after the game is over has happened

  Scenario: <your policy name>  # precedence
    When a card is flipped after the game is over
    Then a card is flipped after the game is over before

  Scenario: <your policy name>  # deadline
    When a card is flipped after the game is over
    Then a card is flipped after the game is over within "30" seconds

```

## `a card is flipped`

- **identity**: `card.flipped.any` (trigger)
- **observes**: event `card.flipped`, entity key `game_id`

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

## `the game is completed`

- **identity**: `game.completed.any` (trigger)
- **observes**: event `game.completed`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the game is completed never happens

  Scenario: <your policy name>  # eventuality
    Then the game is completed has happened

  Scenario: <your policy name>  # precedence
    When the game is completed
    Then the game is completed before

  Scenario: <your policy name>  # deadline
    When the game is completed
    Then the game is completed within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
