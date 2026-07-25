Feature: quarantine containment

  Scenario: a quarantined device performs no non-blocked action
    Given a device is "quarantined"
    Then a device performs a non-blocked action never happens
