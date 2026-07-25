# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a parcel is "{status}"`

- **identity**: `parcel.status.is` (trigger)
- **observes**: event `parcel.status`, entity key `parcel_id`
- **parameters**: `status`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a parcel is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a parcel is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a parcel is "<status>"
    Then a parcel is "<status>" before

  Scenario: <your policy name>  # deadline
    When a parcel is "<status>"
    Then a parcel is "<status>" within "30" seconds

```

## `a parcel is finished`

- **identity**: `parcel.status.finished` (trigger)
- **observes**: event `parcel.status`, entity key `parcel_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a parcel is finished never happens

  Scenario: <your policy name>  # eventuality
    Then a parcel is finished has happened

  Scenario: <your policy name>  # precedence
    When a parcel is finished
    Then a parcel is finished before

  Scenario: <your policy name>  # deadline
    When a parcel is finished
    Then a parcel is finished within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
