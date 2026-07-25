Feature: a disputed payment takes no new charge activity

  Scenario: once a payment is disputed no new charge activity may happen to it
    Given a payment becomes frozen
    Then a payment is authorized or captured never happens
