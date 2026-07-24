# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a hand is dealt`

- **identity**: `hand.dealt.is` (trigger)
- **observes**: event `hand.dealt`, entity key `hand_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a hand is dealt never happens

  Scenario: <your policy name>  # eventuality
    Then a hand is dealt has happened

  Scenario: <your policy name>  # precedence
    When a hand is dealt
    Then a hand is dealt before

  Scenario: <your policy name>  # deadline
    When a hand is dealt
    Then a hand is dealt within "30" seconds

```

## `a card is dealt to the "{to}"`

- **identity**: `hand.card.to` (trigger)
- **observes**: event `hand.card`, entity key `hand_id`
- **parameters**: `to`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a card is dealt to the "<to>" never happens

  Scenario: <your policy name>  # eventuality
    Then a card is dealt to the "<to>" has happened

  Scenario: <your policy name>  # precedence
    When a card is dealt to the "<to>"
    Then a card is dealt to the "<to>" before

  Scenario: <your policy name>  # deadline
    When a card is dealt to the "<to>"
    Then a card is dealt to the "<to>" within "30" seconds

```

## `the hand stands`

- **identity**: `hand.stand.is` (trigger)
- **observes**: event `hand.stand`, entity key `hand_id`

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

## `the "{who}" busts`

- **identity**: `hand.bust.who` (trigger)
- **observes**: event `hand.bust`, entity key `hand_id`
- **parameters**: `who`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the "<who>" busts never happens

  Scenario: <your policy name>  # eventuality
    Then the "<who>" busts has happened

  Scenario: <your policy name>  # precedence
    When the "<who>" busts
    Then the "<who>" busts before

  Scenario: <your policy name>  # deadline
    When the "<who>" busts
    Then the "<who>" busts within "30" seconds

```

## `the hand is settled`

- **identity**: `hand.settled.is` (trigger)
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

## `the hand is settled as a "{outcome}"`

- **identity**: `hand.settled.as` (trigger)
- **observes**: event `hand.settled`, entity key `hand_id`
- **parameters**: `outcome`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand is settled as a "<outcome>" never happens

  Scenario: <your policy name>  # eventuality
    Then the hand is settled as a "<outcome>" has happened

  Scenario: <your policy name>  # precedence
    When the hand is settled as a "<outcome>"
    Then the hand is settled as a "<outcome>" before

  Scenario: <your policy name>  # deadline
    When the hand is settled as a "<outcome>"
    Then the hand is settled as a "<outcome>" within "30" seconds

```

## `a hand is resettled`

- **identity**: `hand.resettled.is` (trigger)
- **observes**: event `hand.resettled`, entity key `hand_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a hand is resettled never happens

  Scenario: <your policy name>  # eventuality
    Then a hand is resettled has happened

  Scenario: <your policy name>  # precedence
    When a hand is resettled
    Then a hand is resettled before

  Scenario: <your policy name>  # deadline
    When a hand is resettled
    Then a hand is resettled within "30" seconds

```

## `a payout happens`

- **identity**: `hand.payout.is` (trigger)
- **observes**: event `hand.payout`, entity key `hand_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payout happens never happens

  Scenario: <your policy name>  # eventuality
    Then a payout happens has happened

  Scenario: <your policy name>  # precedence
    When a payout happens
    Then a payout happens before

  Scenario: <your policy name>  # deadline
    When a payout happens
    Then a payout happens within "30" seconds

```

## `the hand is closed`

- **identity**: `hand.closed.is` (trigger)
- **observes**: event `hand.closed`, entity key `hand_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the hand is closed never happens

  Scenario: <your policy name>  # eventuality
    Then the hand is closed has happened

  Scenario: <your policy name>  # precedence
    When the hand is closed
    Then the hand is closed before

  Scenario: <your policy name>  # deadline
    When the hand is closed
    Then the hand is closed within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
