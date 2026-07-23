# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `the parcel becomes "{status}"`

- **identity**: `parcel.status.is` (trigger)
- **observes**: event `parcel.status`, entity key `parcel_id`
- **parameters**: `status`
- **also writable as**: `a parcel is "{status}"`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the parcel becomes "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then the parcel becomes "<status>" has happened

  Scenario: <your policy name>  # precedence
    When the parcel becomes "<status>"
    Then the parcel becomes "<status>" before

  Scenario: <your policy name>  # deadline
    When the parcel becomes "<status>"
    Then the parcel becomes "<status>" within "30" seconds

```

## `the parcel becomes delivered or returned`

- **identity**: `parcel.status.settled` (trigger)
- **observes**: event `parcel.status`, entity key `parcel_id`
- **also writable as**: `a parcel is delivered or returned`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the parcel becomes delivered or returned never happens

  Scenario: <your policy name>  # eventuality
    Then the parcel becomes delivered or returned has happened

  Scenario: <your policy name>  # precedence
    When the parcel becomes delivered or returned
    Then the parcel becomes delivered or returned before

  Scenario: <your policy name>  # deadline
    When the parcel becomes delivered or returned
    Then the parcel becomes delivered or returned within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
