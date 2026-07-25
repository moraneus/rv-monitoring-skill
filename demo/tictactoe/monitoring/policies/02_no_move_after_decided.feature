Feature: play stops once the game is decided

  # Law 2 (user-stated): "Once a game is won or drawn, no further move may
  # ever be made in it." The move carries after_finish, stamped "yes" only
  # when the board was already decided. A self-contained prohibition (not a
  # scoped one) so a move arriving AFTER the game.over terminal still
  # violates on its fresh instance instead of showing a false green.
  Scenario: no move may be played after the game is won or drawn
    Then a move is played after the game is decided never happens
