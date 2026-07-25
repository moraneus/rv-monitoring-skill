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

## `a booking is confirmed while the member owes`

- **identity**: `booking.status.confirmed_owing` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking is confirmed while the member owes never happens

  Scenario: <your policy name>  # eventuality
    Then a booking is confirmed while the member owes has happened

  Scenario: <your policy name>  # precedence
    When a booking is confirmed while the member owes
    Then a booking is confirmed while the member owes before

  Scenario: <your policy name>  # deadline
    When a booking is confirmed while the member owes
    Then a booking is confirmed while the member owes within "30" seconds

```

## `a booking is confirmed or cancelled`

- **identity**: `booking.status.settled` (trigger)
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

## `a booking reaches an end state`

- **identity**: `booking.status.ended` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking reaches an end state never happens

  Scenario: <your policy name>  # eventuality
    Then a booking reaches an end state has happened

  Scenario: <your policy name>  # precedence
    When a booking reaches an end state
    Then a booking reaches an end state before

  Scenario: <your policy name>  # deadline
    When a booking reaches an end state
    Then a booking reaches an end state within "30" seconds

```

## `a booking breaks the class capacity`

- **identity**: `booking.cap.exceeded` (trigger)
- **observes**: event `booking.cap_exceeded`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking breaks the class capacity never happens

  Scenario: <your policy name>  # eventuality
    Then a booking breaks the class capacity has happened

  Scenario: <your policy name>  # precedence
    When a booking breaks the class capacity
    Then a booking breaks the class capacity before

  Scenario: <your policy name>  # deadline
    When a booking breaks the class capacity
    Then a booking breaks the class capacity within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
