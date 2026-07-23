Feature: renewal precedence

  Scenario: a loan may only be renewed after it was borrowed
    When a loan is "renewed"
    Then a loan is "borrowed" before
