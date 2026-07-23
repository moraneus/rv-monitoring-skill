Feature: quarantine containment

  # Rule 2 (Option A): from the moment a device is quarantined, everything that
  # happens to it must be a "blocked" rejection OR the legitimate decommission
  # wipe -- nothing else. "contained" = status in {blocked, wiped}. This lets
  # the decommission path quarantine -> wipe -> retire stay clean (the wipe is
  # allowed, and retirement is the separate device.retired event, unobserved
  # here), while a normal action after quarantine still violates.
  Scenario: after quarantine a device is only blocked or the decommission wipe
    Then a device is contained since a device is "quarantined"
