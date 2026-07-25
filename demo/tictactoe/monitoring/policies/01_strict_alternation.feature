Feature: turn alternation

  # Law 1 (user-stated): "The players must strictly alternate: immediately
  # after X moves, the very next move in that game must be O's, and vice
  # versa." Two moves in a row by the same mark is the violation. Checked at
  # every move via the app-stamped prev_player field, so it never settles
  # early on a live game.
  Scenario: players must strictly alternate turns
    Then the same player moves twice in a row never happens
