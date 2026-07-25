Feature: a returned loan is never renewed

  Scenario: a returned loan is never renewed afterwards
    Given a loan is "returned"
    Then a loan is "renewed" never happens
