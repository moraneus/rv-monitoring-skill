Feature: a busted hand cannot win

  Scenario: a hand where the player busts is never settled as a win
    Given the "player" busts
    Then the hand is settled as a "win" never happens
