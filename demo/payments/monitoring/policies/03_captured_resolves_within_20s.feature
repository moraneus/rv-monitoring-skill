Feature: a captured payment resolves in time

  Scenario: once captured a payment must be closed or disputed within 20 seconds
    When a payment is "captured"
    Then a payment is disputed or closed within "20" seconds
