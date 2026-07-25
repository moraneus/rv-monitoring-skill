Feature: a loan is renewed only after it was borrowed

  Scenario: a loan can only be renewed after it was borrowed
    When a loan is "renewed"
    Then a loan is "borrowed" before
