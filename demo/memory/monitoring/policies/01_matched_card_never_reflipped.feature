Feature: matched cards stay put

  # Rule 1: a card that is part of a found match must never be flipped again
  # for the rest of that game. Checked on every flip via the history-stamped
  # `already_matched` field, so it never settles early.
  Scenario: a matched card is never flipped again
    Then a matched card is flipped again never happens
