Feature: a finished game stays finished

  # Rule 3: once the last pair is found the game is complete - nothing may
  # ever happen in that game again. game.completed is the terminal event, so
  # any post-completion flip spawns a fresh monitor instance that violates
  # immediately (the self-contained `never` has no terminal-window blind spot).
  Scenario: nothing happens after the game is over
    Then a card is flipped after the game is over never happens
