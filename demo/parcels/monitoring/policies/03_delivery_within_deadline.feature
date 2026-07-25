Feature: delivery deadline

  Scenario: a parcel out for delivery is delivered or returned within 12 seconds
    When a parcel is "out_for_delivery"
    Then a parcel is finished within "12" seconds
