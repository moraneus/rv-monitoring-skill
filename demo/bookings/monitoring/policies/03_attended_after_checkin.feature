Feature: attendance requires check-in

  Scenario: a booking is only marked attended after check-in
    When a booking is "attended"
    Then a booking is "checked_in" before
