Feature: sensor feed health

  Scenario: a sensor feed only ever reports ok readings
    Then a sensor reading is "ok" always holds
