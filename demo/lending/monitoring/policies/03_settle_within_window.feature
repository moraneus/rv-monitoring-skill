Feature: no loan is left hanging

  Scenario: every borrowed loan is returned, renewed or reported lost within 21 seconds
    When a loan is "borrowed"
    Then a loan is renewed, returned or reported lost within "21" seconds
