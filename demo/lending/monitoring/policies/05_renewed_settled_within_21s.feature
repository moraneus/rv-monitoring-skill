Feature: renewal deadline

  Scenario: a renewed loan is settled again within 21 seconds
    When a loan is "renewed"
    Then a loan is renewed, returned, or reported lost within "21" seconds
