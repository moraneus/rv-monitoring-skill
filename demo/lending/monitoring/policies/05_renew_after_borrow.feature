Feature: renewal discipline

  Scenario: a loan is only renewed after it was borrowed
    When a loan is "renewed"
    Then a loan is "borrowed" before
