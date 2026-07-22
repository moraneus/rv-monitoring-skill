Feature: __ENTITY__ lifecycle safety

  Scenario: a __ENTITY__ is only completed after it was started
    When a __ENTITY__ is "completed"
    Then a __ENTITY__ is "started" before
