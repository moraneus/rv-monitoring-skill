Feature: attempts resolve promptly

  # Rule 2: after the second card of an attempt is flipped, the attempt must
  # resolve - matched or both flipped back - within 3 seconds. Keyed per
  # attempt: the trigger is the second card being up (attempt ready), the
  # response is the resolution; the deadline fires on absence.
  Scenario: a pending attempt resolves within three seconds
    When an attempt is ready
    Then an attempt is resolved within "3" seconds
