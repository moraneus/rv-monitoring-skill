Feature: Only confirmed bookings check in

  Scenario: a booking checks in without being confirmed first
    When a booking is "checked_in"
    Then a booking is "confirmed" before
