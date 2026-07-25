Feature: no reroute after delivery

  Scenario: a delivered parcel must never be re-routed
    Given a parcel is "delivered"
    Then a parcel is "rerouted" never happens
