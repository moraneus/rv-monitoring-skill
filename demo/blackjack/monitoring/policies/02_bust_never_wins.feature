Feature: a busted hand never wins

  Scenario: a hand that busts is never settled as a win
    Given the hand busts
    Then the hand is settled as "win" never happens
