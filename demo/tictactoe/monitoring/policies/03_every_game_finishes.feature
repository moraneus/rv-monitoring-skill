Feature: every game reaches an end

  # Law 3 (user-stated): "Every game that starts must eventually finish -
  # won or drawn, none abandoned forever." An eventuality: it holds pending
  # while the game is in progress, satisfies when the board is decided, and
  # violates at the game.over terminal if the game ended abandoned (a game
  # replaced or reset before it was decided).
  Scenario: every game that starts must eventually be decided
    Then a game is decided has happened
