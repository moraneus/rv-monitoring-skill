# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a payment is "{status}"`

- **identity**: `payment.status.is` (trigger)
- **observes**: event `payment.status`, entity key `payment_id`
- **parameters**: `status`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payment is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a payment is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a payment is "<status>"
    Then a payment is "<status>" before

  Scenario: <your policy name>  # deadline
    When a payment is "<status>"
    Then a payment is "<status>" within "30" seconds

```

## `a payment changes status`

- **identity**: `payment.status.any` (obligation)
- **observes**: event `payment.status`, entity key `payment_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payment changes status never happens

  Scenario: <your policy name>  # eventuality
    Then a payment changes status has happened

  Scenario: <your policy name>  # precedence
    When a payment changes status
    Then a payment changes status before

  Scenario: <your policy name>  # deadline
    When a payment changes status
    Then a payment changes status within "30" seconds

```

## `a payment is disputed or closed`

- **identity**: `payment.status.resolved` (trigger)
- **observes**: event `payment.status`, entity key `payment_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payment is disputed or closed never happens

  Scenario: <your policy name>  # eventuality
    Then a payment is disputed or closed has happened

  Scenario: <your policy name>  # precedence
    When a payment is disputed or closed
    Then a payment is disputed or closed before

  Scenario: <your policy name>  # deadline
    When a payment is disputed or closed
    Then a payment is disputed or closed within "30" seconds

```

## `a payment is authorized or captured`

- **identity**: `payment.status.charge` (obligation)
- **observes**: event `payment.status`, entity key `payment_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payment is authorized or captured never happens

  Scenario: <your policy name>  # eventuality
    Then a payment is authorized or captured has happened

  Scenario: <your policy name>  # precedence
    When a payment is authorized or captured
    Then a payment is authorized or captured before

  Scenario: <your policy name>  # deadline
    When a payment is authorized or captured
    Then a payment is authorized or captured within "30" seconds

```

## `a disputed payment closes`

- **identity**: `payment.dispute_closed.is` (trigger)
- **observes**: event `payment.dispute_closed`, entity key `payment_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a disputed payment closes never happens

  Scenario: <your policy name>  # eventuality
    Then a disputed payment closes has happened

  Scenario: <your policy name>  # precedence
    When a disputed payment closes
    Then a disputed payment closes before

  Scenario: <your policy name>  # deadline
    When a disputed payment closes
    Then a disputed payment closes within "30" seconds

```

## `a payment becomes frozen`

- **identity**: `payment.frozen.mark` (scope)
- **observes**: event `payment.frozen`, entity key `payment_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payment becomes frozen never happens

  Scenario: <your policy name>  # eventuality
    Then a payment becomes frozen has happened

  Scenario: <your policy name>  # precedence
    When a payment becomes frozen
    Then a payment becomes frozen before

  Scenario: <your policy name>  # deadline
    When a payment becomes frozen
    Then a payment becomes frozen within "30" seconds

```

## `a payment is frozen-rejected`

- **identity**: `payment.rejected.frozen` (trigger)
- **observes**: event `payment.rejected`, entity key `payment_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a payment is frozen-rejected never happens

  Scenario: <your policy name>  # eventuality
    Then a payment is frozen-rejected has happened

  Scenario: <your policy name>  # precedence
    When a payment is frozen-rejected
    Then a payment is frozen-rejected before

  Scenario: <your policy name>  # deadline
    When a payment is frozen-rejected
    Then a payment is frozen-rejected within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
