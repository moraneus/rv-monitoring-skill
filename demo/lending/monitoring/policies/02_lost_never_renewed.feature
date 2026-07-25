Feature: a lost loan is never renewed

  Scenario: once a loan is reported lost it must never be renewed
    Given a loan is "lost"
    Then a loan is "renewed" never happens
