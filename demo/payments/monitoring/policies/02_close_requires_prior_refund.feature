Feature: a disputed payment is refunded before it closes

  Scenario: every disputed payment that closes must have been refunded first
    When a disputed payment closes
    Then a payment is "refunded" before
