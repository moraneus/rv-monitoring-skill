# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values -
use the exact strings listed under each step (a value the app never
emits will compile but silently never match).
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a loan is "{status}"`

- **identity**: `loan.status.is` (trigger)
- **observes**: event `loan.status`, entity key `loan_id`
- **parameters**: `status`
  - `status` values seen in the recorded trace: `borrowed`, `lost`, `renewed`, `returned`

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

## `a loan is returned, renewed, or reported lost`

- **identity**: `loan.status.settled` (trigger)
- **observes**: event `loan.status`, entity key `loan_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a loan is returned, renewed, or reported lost never happens

  Scenario: <your policy name>  # eventuality
    Then a loan is returned, renewed, or reported lost has happened

  Scenario: <your policy name>  # precedence
    When a loan is returned, renewed, or reported lost
    Then a loan is returned, renewed, or reported lost before

  Scenario: <your policy name>  # deadline
    When a loan is returned, renewed, or reported lost
    Then a loan is returned, renewed, or reported lost within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
