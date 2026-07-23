Feature: sensor feed health

  # Rule 4: a sensor feed must only ever report readings with status "ok" --
  # any other reading status is a violation for that sensor. "every event is a
  # P event" -> always holds.
  Scenario: a sensor feed only ever reports ok readings
    Then a sensor reading is "ok" always holds
