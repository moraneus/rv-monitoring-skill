Feature: a payout only follows settlement

  Scenario: a payout only happens after the hand is settled
    When a payout happens
    Then the hand is settled before
