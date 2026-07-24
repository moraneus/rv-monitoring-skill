Feature: standing locks the hand

  Scenario: a hand that has stood is never dealt another card
    Given the hand stands
    Then a card is dealt to the "player" never happens
