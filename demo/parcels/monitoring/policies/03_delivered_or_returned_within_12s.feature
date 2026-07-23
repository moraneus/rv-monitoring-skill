Feature: out-for-delivery resolves in time

  Scenario: an out-for-delivery parcel is delivered or returned within 12 seconds
    When a parcel is "out_for_delivery"
    Then a parcel is delivered or returned within "12" seconds
