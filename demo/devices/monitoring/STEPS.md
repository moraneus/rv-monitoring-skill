# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a device is "{status}"`

- **identity**: `device.status.is` (trigger)
- **observes**: event `device.status`, entity key `device_id`
- **parameters**: `status`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device is "<status>" never happens

  Scenario: <your policy name>  # eventuality
    Then a device is "<status>" has happened

  Scenario: <your policy name>  # precedence
    When a device is "<status>"
    Then a device is "<status>" before

  Scenario: <your policy name>  # deadline
    When a device is "<status>"
    Then a device is "<status>" within "30" seconds

```

## `a device acts "{result}"`

- **identity**: `device.action.result` (trigger)
- **observes**: event `device.action`, entity key `device_id`
- **parameters**: `result`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device acts "<result>" never happens

  Scenario: <your policy name>  # eventuality
    Then a device acts "<result>" has happened

  Scenario: <your policy name>  # precedence
    When a device acts "<result>"
    Then a device acts "<result>" before

  Scenario: <your policy name>  # deadline
    When a device acts "<result>"
    Then a device acts "<result>" within "30" seconds

```

## `a device is retired`

- **identity**: `device.retired.is` (trigger)
- **observes**: event `device.retired`, entity key `device_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device is retired never happens

  Scenario: <your policy name>  # eventuality
    Then a device is retired has happened

  Scenario: <your policy name>  # precedence
    When a device is retired
    Then a device is retired before

  Scenario: <your policy name>  # deadline
    When a device is retired
    Then a device is retired within "30" seconds

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

## `a device is rejected or decommissioned`

- **identity**: `device.contained.is` (trigger)
- **observes**: event `device.action`, entity key `device_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device is rejected or decommissioned never happens

  Scenario: <your policy name>  # eventuality
    Then a device is rejected or decommissioned has happened

  Scenario: <your policy name>  # precedence
    When a device is rejected or decommissioned
    Then a device is rejected or decommissioned before

  Scenario: <your policy name>  # deadline
    When a device is rejected or decommissioned
    Then a device is rejected or decommissioned within "30" seconds

```

## `a quarantine surge is flagged`

- **identity**: `fleet.quarantine.surge` (trigger)
- **observes**: event `fleet.quarantine`, entity key `fleet_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a quarantine surge is flagged never happens

  Scenario: <your policy name>  # eventuality
    Then a quarantine surge is flagged has happened

  Scenario: <your policy name>  # precedence
    When a quarantine surge is flagged
    Then a quarantine surge is flagged before

  Scenario: <your policy name>  # deadline
    When a quarantine surge is flagged
    Then a quarantine surge is flagged within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
