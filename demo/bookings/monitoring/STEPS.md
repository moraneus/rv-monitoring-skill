# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a booking is "{status}"`

- **identity**: `booking.status.is` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`
- **parameters**: `status`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a booking is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a booking is "<status>"
    Then a booking is "<status>" before

  Scenario: <your policy name>  # deadline
    When a booking is "<status>"
    Then a booking is "<status>" within "30" seconds

```

## `a booking reaches a final state`

- **identity**: `booking.final.reached` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking reaches a final state never happens

  Scenario: <your policy name>  # eventuality
    Then a booking reaches a final state has happened

  Scenario: <your policy name>  # precedence
    When a booking reaches a final state
    Then a booking reaches a final state before

  Scenario: <your policy name>  # deadline
    When a booking reaches a final state
    Then a booking reaches a final state within "30" seconds

```

## `a booking is confirmed or cancelled`

- **identity**: `booking.promo.answered` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking is confirmed or cancelled never happens

  Scenario: <your policy name>  # eventuality
    Then a booking is confirmed or cancelled has happened

  Scenario: <your policy name>  # precedence
    When a booking is confirmed or cancelled
    Then a booking is confirmed or cancelled before

  Scenario: <your policy name>  # deadline
    When a booking is confirmed or cancelled
    Then a booking is confirmed or cancelled within "30" seconds

```

## `a member's balance is "{state}"`

- **identity**: `member.balance.is` (trigger)
- **observes**: event `member.balance`, entity key `member_id`
- **parameters**: `state`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a member's balance is "<state>" never happens

  Scenario: <your policy name>  # eventuality
    Then a member's balance is "<state>" has happened

  Scenario: <your policy name>  # precedence
    When a member's balance is "<state>"
    Then a member's balance is "<state>" before

  Scenario: <your policy name>  # deadline
    When a member's balance is "<state>"
    Then a member's balance is "<state>" within "30" seconds

```

## `a member confirms a booking`

- **identity**: `member.booking.confirmed` (trigger)
- **observes**: event `member.booking_confirmed`, entity key `member_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a member confirms a booking never happens

  Scenario: <your policy name>  # eventuality
    Then a member confirms a booking has happened

  Scenario: <your policy name>  # precedence
    When a member confirms a booking
    Then a member confirms a booking before

  Scenario: <your policy name>  # deadline
    When a member confirms a booking
    Then a member confirms a booking within "30" seconds

```

## `a seat is "confirmed"`

- **identity**: `seat.confirmed.is` (trigger)
- **observes**: event `seat.confirmed`, entity key `member_id, class_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a seat is "confirmed" never happens

  Scenario: <your policy name>  # eventuality
    Then a seat is "confirmed" has happened

  Scenario: <your policy name>  # precedence
    When a seat is "confirmed"
    Then a seat is "confirmed" before

  Scenario: <your policy name>  # deadline
    When a seat is "confirmed"
    Then a seat is "confirmed" within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
