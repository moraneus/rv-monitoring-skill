Feature: cancelled bookings

  Scenario: a cancelled booking is never checked in
    Given a booking is "cancelled"
    Then a booking is "checked_in" never happens
