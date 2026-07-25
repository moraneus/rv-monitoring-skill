Feature: no scoring after a game is over

  Scenario: a finished game never scores again
    Given a game is "over"
    Then a point is scored never happens
