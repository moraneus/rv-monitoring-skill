Feature: no play after a game is over

  Scenario: a finished game never moves again
    Given a game is "over"
    Then the snake moves never happens
