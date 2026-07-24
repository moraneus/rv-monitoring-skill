Feature: nothing happens before a game has started

  Scenario: no move occurs before the game has started
    When a move is made
    Then a game is "started" before

  Scenario: no points are scored before the game has started
    When points are scored
    Then a game is "started" before
