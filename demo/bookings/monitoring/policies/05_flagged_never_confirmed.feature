Feature: Flagged bookings are never confirmed

  Scenario: a booking flagged as duplicate or over capacity is confirmed
    Then a booking is confirmed despite a capacity or duplicate flag never happens
