Feature: match integrity

  # A card must have been flipped (revealed) before it can be reported matched.
  # A card.matched with no preceding card.flip for that card is a match appearing
  # out of nowhere - stream corruption - and this catches it per card. Keyed per
  # card (game_id, position); decided at the card.matched event.
  Scenario: every matched card was flipped first
    When a card is matched
    Then a card is flipped before
