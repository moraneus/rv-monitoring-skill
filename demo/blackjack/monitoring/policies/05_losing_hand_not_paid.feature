Feature: losing hands are not paid

  Scenario: a hand settled as a loss is never paid out
    Given the hand is settled as "lose"
    Then a payout is made for the hand never happens
