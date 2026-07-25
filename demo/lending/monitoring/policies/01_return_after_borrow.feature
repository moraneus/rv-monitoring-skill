Feature: a loan is returned only after it was borrowed

  Scenario: a loan can only be returned after it was borrowed
    When a loan is "returned"
    Then a loan is "borrowed" before
