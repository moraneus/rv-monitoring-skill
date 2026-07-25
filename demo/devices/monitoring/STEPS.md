# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a device is "{state}"`

- **identity**: `device.lifecycle.is` (trigger)
- **observes**: event `device.lifecycle`, entity key `device_id`
- **parameters**: `state`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device is "<state>" never happens

  Scenario: <your policy name>  # eventuality
    Then a device is "<state>" has happened

  Scenario: <your policy name>  # precedence
    When a device is "<state>"
    Then a device is "<state>" before

  Scenario: <your policy name>  # deadline
    When a device is "<state>"
    Then a device is "<state>" within "30" seconds

```

## `a device action is "{result}"`

- **identity**: `device.action.is` (trigger)
- **observes**: event `device.action`, entity key `device_id`
- **parameters**: `result`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device action is "<result>" never happens

  Scenario: <your policy name>  # eventuality
    Then a device action is "<result>" has happened

  Scenario: <your policy name>  # precedence
    When a device action is "<result>"
    Then a device action is "<result>" before

  Scenario: <your policy name>  # deadline
    When a device action is "<result>"
    Then a device action is "<result>" within "30" seconds

```

## `a device performs a non-blocked action`

- **identity**: `device.action.non_blocked` (trigger)
- **observes**: event `device.action`, entity key `device_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device performs a non-blocked action never happens

  Scenario: <your policy name>  # eventuality
    Then a device performs a non-blocked action has happened

  Scenario: <your policy name>  # precedence
    When a device performs a non-blocked action
    Then a device performs a non-blocked action before

  Scenario: <your policy name>  # deadline
    When a device performs a non-blocked action
    Then a device performs a non-blocked action within "30" seconds

```

## `a sensor reading is "{status}"`

- **identity**: `sensor.reading.is` (trigger)
- **observes**: event `sensor.reading`, entity key `sensor_id`
- **parameters**: `status`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a sensor reading is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a sensor reading is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a sensor reading is "<status>"
    Then a sensor reading is "<status>" before

  Scenario: <your policy name>  # deadline
    When a sensor reading is "<status>"
    Then a sensor reading is "<status>" within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
