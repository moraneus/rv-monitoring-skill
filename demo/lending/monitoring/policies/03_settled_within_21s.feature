Feature: every borrowed loan is settled in time

  Scenario: a borrowed loan is returned, renewed, or reported lost within 21 seconds
    When a loan is "borrowed"
    Then a loan is returned, renewed, or reported lost within "21" seconds
