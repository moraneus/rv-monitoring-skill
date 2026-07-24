Feature: eating makes the snake grow promptly

  Scenario: every eaten food makes the snake grow within two seconds
    When the snake eats food
    Then the snake grows within "2" seconds
