Feature: Attendance follows a check-in

  Scenario: a booking is marked attended without a check-in
    When a booking is "attended"
    Then a booking is "checked_in" before
