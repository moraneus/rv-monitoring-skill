Feature: a found match is final

  # Rule 1: a card that is part of a found match must never be flipped again
  # for the rest of that game. Keyed per card (game_id, position): the scope
  # opens when the card is matched and never closes, so any later flip of that
  # same card violates.
  Scenario: a matched card is never flipped again
    Given a card is matched
    Then a card is flipped never happens
