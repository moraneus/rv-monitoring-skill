Feature: a detonated board is frozen

  Scenario: no cell is revealed after a mine explodes
    Given a mine explodes
    Then a cell is revealed on the board never happens
