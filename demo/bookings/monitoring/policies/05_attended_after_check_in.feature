Feature: attendance integrity

  Scenario: a booking is only attended after it was checked in
    When a booking is "attended"
    Then a booking is "checked_in" before
