Feature: every hand reaches settlement in time

  Scenario: every dealt hand is settled within 30 seconds
    When a hand is dealt
    Then the hand is settled within "30" seconds
