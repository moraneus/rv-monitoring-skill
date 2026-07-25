Feature: each square is revealed at most once

  Scenario: a cell is never revealed twice
    Given that cell was already revealed
    Then a cell is revealed never happens
