Feature: attempts resolve promptly

  # Rule 2: after the second card of an attempt is flipped, the attempt must
  # resolve - matched or both flipped back - within 3 seconds. Keyed per
  # attempt (game_id, attempt_id) so EVERY attempt's deadline is checked, not
  # just the first one of the game.
  Scenario: an attempt resolves within 3 seconds
    When the second card of an attempt is flipped
    Then the attempt resolves within "3" seconds
