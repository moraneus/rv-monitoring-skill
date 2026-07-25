Feature: a stood hand takes no more cards

  Scenario: once a hand stands it is never dealt another card
    Given the hand stands
    Then the hand is dealt a card never happens
