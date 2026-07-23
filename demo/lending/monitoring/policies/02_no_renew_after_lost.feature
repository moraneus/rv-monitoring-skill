Feature: lost loans are frozen

  Scenario: once a loan is reported lost it is never renewed
    Given a loan is "lost"
    Then a loan is "renewed" never happens
