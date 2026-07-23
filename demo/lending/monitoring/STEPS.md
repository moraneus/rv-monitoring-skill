# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a loan is "{status}"`

- **identity**: `loan.status.is` (trigger)
- **observes**: event `loan.status`, entity key `loan_id`
- **parameters**: `status`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a loan is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a loan is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a loan is "<status>"
    Then a loan is "<status>" before

  Scenario: <your policy name>  # deadline
    When a loan is "<status>"
    Then a loan is "<status>" within "30" seconds

```

## `a loan is renewed, returned or reported lost`

- **identity**: `loan.status.settled_or_renewed` (trigger)
- **observes**: event `loan.status`, entity key `loan_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a loan is renewed, returned or reported lost never happens

  Scenario: <your policy name>  # eventuality
    Then a loan is renewed, returned or reported lost has happened

  Scenario: <your policy name>  # precedence
    When a loan is renewed, returned or reported lost
    Then a loan is renewed, returned or reported lost before

  Scenario: <your policy name>  # deadline
    When a loan is renewed, returned or reported lost
    Then a loan is renewed, returned or reported lost within "30" seconds

```

## `a member's fine is "{state}"`

- **identity**: `member.fine.is` (trigger)
- **observes**: event `member.fine`, entity key `member_id`
- **parameters**: `state`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a member's fine is "<state>" never happens

  Scenario: <your policy name>  # eventuality
    Then a member's fine is "<state>" has happened

  Scenario: <your policy name>  # precedence
    When a member's fine is "<state>"
    Then a member's fine is "<state>" before

  Scenario: <your policy name>  # deadline
    When a member's fine is "<state>"
    Then a member's fine is "<state>" within "30" seconds

```

## `a member renews a loan`

- **identity**: `member.renewal.happened` (trigger)
- **observes**: event `member.renewal`, entity key `member_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a member renews a loan never happens

  Scenario: <your policy name>  # eventuality
    Then a member renews a loan has happened

  Scenario: <your policy name>  # precedence
    When a member renews a loan
    Then a member renews a loan before

  Scenario: <your policy name>  # deadline
    When a member renews a loan
    Then a member renews a loan within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
