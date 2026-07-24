Feature: a game is over once a mine explodes

  Scenario: no cell is revealed after a mine explodes
    Given a mine explodes
    Then a cell is revealed never happens
