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

## `a device is contained`

- **identity**: `device.status.contained` (trigger)
- **observes**: event `device.status`, entity key `device_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a device is contained never happens

  Scenario: <your policy name>  # eventuality
    Then a device is contained has happened

  Scenario: <your policy name>  # precedence
    When a device is contained
    Then a device is contained before

  Scenario: <your policy name>  # deadline
    When a device is contained
    Then a device is contained within "30" seconds

```

## `a device is retired`

- **identity**: `device.retired` (trigger)
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

## `the fleet quarantine level is "{level}"`

- **identity**: `fleet.quarantine.level` (trigger)
- **observes**: event `fleet.quarantine`, entity key `fleet_id`
- **parameters**: `level`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the fleet quarantine level is "<level>" never happens

  Scenario: <your policy name>  # eventuality
    Then the fleet quarantine level is "<level>" has happened

  Scenario: <your policy name>  # precedence
    When the fleet quarantine level is "<level>"
    Then the fleet quarantine level is "<level>" before

  Scenario: <your policy name>  # deadline
    When the fleet quarantine level is "<level>"
    Then the fleet quarantine level is "<level>" within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
