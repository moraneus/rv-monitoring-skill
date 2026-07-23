Feature: delivered parcels are never re-routed

  Scenario: once a parcel is delivered it must never be re-routed
    Given a parcel is "delivered"
    Then a parcel is "rerouted" never happens
