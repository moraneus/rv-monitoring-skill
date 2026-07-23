Feature: quarantine containment

  Scenario: a quarantined device may only perform blocked actions
    Given a device is "quarantined"
    Then a device acts "ok" never happens
