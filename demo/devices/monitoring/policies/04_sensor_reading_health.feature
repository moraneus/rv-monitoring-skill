Feature: sensor reading health

  Scenario: a sensor feed must only ever report ok readings
    Then a sensor reading is "ok" always holds
