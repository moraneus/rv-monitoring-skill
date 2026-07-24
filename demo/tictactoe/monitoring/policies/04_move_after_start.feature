Feature: no orphan moves

  Scenario: a move only happens after its game has started
    When a move is made
    Then a game is started before
