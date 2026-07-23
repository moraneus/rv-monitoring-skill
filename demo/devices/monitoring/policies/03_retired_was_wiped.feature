Feature: retirement safety

  # Rule 3: every retired device must have been wiped at some point before
  # retirement. "X must have happened before Y" -> before (any earlier point),
  # decided at the retirement trigger.
  Scenario: a retired device was wiped beforehand
    When a device is retired
    Then a device is "wiped" before
