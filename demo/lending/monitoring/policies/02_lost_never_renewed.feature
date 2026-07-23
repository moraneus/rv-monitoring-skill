Feature: lost loan safety

  Scenario: a loan reported lost is never renewed
    Given a loan is "lost"
    Then a loan is "renewed" never happens
