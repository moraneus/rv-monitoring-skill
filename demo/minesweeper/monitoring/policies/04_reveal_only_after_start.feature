Feature: the board exists before it is played

  Scenario: a cell is only revealed after the game has started
    When a cell is revealed
    Then the game has started before
