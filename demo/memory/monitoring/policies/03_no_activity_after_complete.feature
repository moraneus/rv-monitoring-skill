Feature: a completed game is finished forever

  # Rule 3: once the last pair is found the game is complete - nothing may ever
  # happen in that game again. Keyed per game: the scope opens at completion and
  # never closes, so any later game action violates.
  #
  # game.complete is deliberately NOT a terminal event: a terminal would settle
  # this prohibition as satisfied and blind it to post-completion activity (a
  # false green). The game entity is reclaimed by the quiescence TTL instead, so
  # the rule stays armed after completion.
  Scenario: nothing happens after the game is complete
    Given the game is complete
    Then a game action occurs never happens
