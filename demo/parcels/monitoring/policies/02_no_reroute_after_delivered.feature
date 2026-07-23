Feature: delivery is final

  Scenario: a delivered parcel is never re-routed
    Given a parcel is "delivered"
    Then a parcel is "rerouted" never happens
