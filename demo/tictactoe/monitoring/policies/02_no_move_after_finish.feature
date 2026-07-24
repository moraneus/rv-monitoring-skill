Feature: no move after a finished game

  Scenario: once a game is won or drawn, no further move is ever made
    Given a game is finished
    Then a move is made never happens
