Feature: every point scored makes the snake grow in time

  Scenario: food eaten is followed by growth within two seconds
    When food is eaten
    Then the snake grows within "2" seconds
