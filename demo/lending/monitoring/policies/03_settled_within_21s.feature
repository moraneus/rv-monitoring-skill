Feature: loan settlement deadline

  Scenario: a borrowed loan is returned, renewed, or reported lost within 21 seconds
    When a loan is "borrowed"
    Then a loan is renewed, returned, or reported lost within "21" seconds
