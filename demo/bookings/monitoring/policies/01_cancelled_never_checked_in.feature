Feature: A cancelled booking never returns

  Scenario: a cancelled booking is later checked in
    Given a booking is "cancelled"
    Then a booking is "checked_in" never happens
