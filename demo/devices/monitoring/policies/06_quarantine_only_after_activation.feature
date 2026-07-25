Feature: quarantine readiness

  Scenario: a device is only quarantined after it was activated
    When a device is "quarantined"
    Then a device is "activated" before
