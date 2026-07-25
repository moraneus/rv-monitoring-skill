Feature: check-in requires payment

  Scenario: a booking is only checked in after it was confirmed
    When a booking is "checked_in"
    Then a booking is "confirmed" before
