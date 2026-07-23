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

## `a booking is confirmed while the member owes money`

- **identity**: `booking.confirmed.owing` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking is confirmed while the member owes money never happens

  Scenario: <your policy name>  # eventuality
    Then a booking is confirmed while the member owes money has happened

  Scenario: <your policy name>  # precedence
    When a booking is confirmed while the member owes money
    Then a booking is confirmed while the member owes money before

  Scenario: <your policy name>  # deadline
    When a booking is confirmed while the member owes money
    Then a booking is confirmed while the member owes money within "30" seconds

```

## `a booking is confirmed despite a capacity or duplicate flag`

- **identity**: `booking.confirmed.flagged` (trigger)
- **observes**: event `booking.status`, entity key `booking_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a booking is confirmed despite a capacity or duplicate flag never happens

  Scenario: <your policy name>  # eventuality
    Then a booking is confirmed despite a capacity or duplicate flag has happened

  Scenario: <your policy name>  # precedence
    When a booking is confirmed despite a capacity or duplicate flag
    Then a booking is confirmed despite a capacity or duplicate flag before

  Scenario: <your policy name>  # deadline
    When a booking is confirmed despite a capacity or duplicate flag
    Then a booking is confirmed despite a capacity or duplicate flag within "30" seconds

```

## `a booking is confirmed or cancelled`

- **identity**: `booking.resolution` (trigger)
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

- **identity**: `booking.ended` (trigger)
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

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
