Feature: hub scan precedes delivery

  Scenario: a parcel must be scanned at a hub before it goes out for delivery
    When a parcel is "out_for_delivery"
    Then a parcel is "scanned" before
