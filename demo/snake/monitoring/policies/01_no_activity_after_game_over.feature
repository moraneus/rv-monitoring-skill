Feature: no activity after a game is over

  Scenario: a finished game accepts no further moves
    Given a game is "over"
    Then a move is made never happens

  Scenario: a finished game scores no further points
    Given a game is "over"
    Then points are scored never happens
