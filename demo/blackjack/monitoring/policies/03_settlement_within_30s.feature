Feature: every hand settles in time

  Scenario: a dealt hand reaches settlement within 30 seconds
    When the hand is dealt a card
    Then the hand is settled within "30" seconds
