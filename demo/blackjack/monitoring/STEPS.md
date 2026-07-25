# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `the hand is dealt a card`

- **identity**: `hand.dealt.card` (trigger)
- **observes**: event `hand.dealt`, entity key `hand_id`
- **also writable as**: `a card is dealt to the hand`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand is dealt a card never happens

  Scenario: <your policy name>  # eventuality
    Then the hand is dealt a card has happened

  Scenario: <your policy name>  # precedence
    When the hand is dealt a card
    Then the hand is dealt a card before

  Scenario: <your policy name>  # deadline
    When the hand is dealt a card
    Then the hand is dealt a card within "30" seconds

```

## `the hand stands`

- **identity**: `hand.stood` (trigger)
- **observes**: event `hand.stood`, entity key `hand_id`
- **also writable as**: `the player stands`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand stands never happens

  Scenario: <your policy name>  # eventuality
    Then the hand stands has happened

  Scenario: <your policy name>  # precedence
    When the hand stands
    Then the hand stands before

  Scenario: <your policy name>  # deadline
    When the hand stands
    Then the hand stands within "30" seconds

```

## `the hand busts`

- **identity**: `hand.busted` (trigger)
- **observes**: event `hand.busted`, entity key `hand_id`
- **also writable as**: `the hand goes bust`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand busts never happens

  Scenario: <your policy name>  # eventuality
    Then the hand busts has happened

  Scenario: <your policy name>  # precedence
    When the hand busts
    Then the hand busts before

  Scenario: <your policy name>  # deadline
    When the hand busts
    Then the hand busts within "30" seconds

```

## `the hand is settled`

- **identity**: `hand.settled.any` (trigger)
- **observes**: event `hand.settled`, entity key `hand_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand is settled never happens

  Scenario: <your policy name>  # eventuality
    Then the hand is settled has happened

  Scenario: <your policy name>  # precedence
    When the hand is settled
    Then the hand is settled before

  Scenario: <your policy name>  # deadline
    When the hand is settled
    Then the hand is settled within "30" seconds

```

## `the hand is settled as "{outcome}"`

- **identity**: `hand.settled.outcome` (trigger)
- **observes**: event `hand.settled`, entity key `hand_id`
- **parameters**: `outcome`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand is settled as "<outcome>" never happens

  Scenario: <your policy name>  # eventuality
    Then the hand is settled as "<outcome>" has happened

  Scenario: <your policy name>  # precedence
    When the hand is settled as "<outcome>"
    Then the hand is settled as "<outcome>" before

  Scenario: <your policy name>  # deadline
    When the hand is settled as "<outcome>"
    Then the hand is settled as "<outcome>" within "30" seconds

```

## `a payout is made for the hand`

- **identity**: `hand.payout` (trigger)
- **observes**: event `hand.payout`, entity key `hand_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payout is made for the hand never happens

  Scenario: <your policy name>  # eventuality
    Then a payout is made for the hand has happened

  Scenario: <your policy name>  # precedence
    When a payout is made for the hand
    Then a payout is made for the hand before

  Scenario: <your policy name>  # deadline
    When a payout is made for the hand
    Then a payout is made for the hand within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
