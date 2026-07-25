Feature: device action readiness

  Scenario: a device performs actions only after it was activated
    When a device action is "ok"
    Then a device is "activated" before
