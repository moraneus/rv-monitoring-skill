Feature: wipe before retirement

  Scenario: a retired device must have been wiped before retirement
    When a device is retired
    Then a device is "wiped" before
