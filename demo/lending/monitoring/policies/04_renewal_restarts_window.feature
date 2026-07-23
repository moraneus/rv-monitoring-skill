Feature: renewals do not stall

  Scenario: each renewal is itself followed by a settlement within 21 seconds
    When a loan is "renewed"
    Then a loan is renewed, returned or reported lost within "21" seconds
