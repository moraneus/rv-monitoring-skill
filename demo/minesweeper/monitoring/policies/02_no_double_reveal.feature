Feature: a revealed cell stays revealed exactly once

  Scenario: no cell is ever revealed twice
    Given the same cell has been revealed
    Then the same cell is revealed again never happens
