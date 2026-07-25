Feature: a payout only follows settlement

  Scenario: a payout is made only after the hand is settled
    When a payout is made for the hand
    Then the hand is settled before
