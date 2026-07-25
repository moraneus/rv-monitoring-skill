Feature: retirement safety

  Scenario: every retired device was wiped before retirement
    When a device is "retired"
    Then a device is "wiped" before
