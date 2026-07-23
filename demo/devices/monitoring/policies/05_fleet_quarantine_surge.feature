Feature: fleet-wide quarantine surge

  # Rule 5: alert whenever more than 3 devices are in quarantine at the same
  # time (an attack-wave smell). "More than 3 devices at once" is a cross-entity
  # count -- out of the per-entity fragment as stated. The application counts
  # concurrent quarantines (FleetCounter) and emits a singleton fleet.quarantine
  # "surge" event on the upward crossing; this policy turns that surge into the
  # alert. Single-shot per fleet: the first surge violates (= alert) and settles.
  Scenario: more than three devices are never quarantined at once
    Then the fleet quarantine level is "surge" never happens
