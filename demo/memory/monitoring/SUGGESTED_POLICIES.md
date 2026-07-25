# Suggested policies

You (the human) own the policies. These are proposals only - nothing here is
active until you move it into `monitoring/policies/` yourself. Each one below
compiles against the current registry and was mini-replayed on healthy traffic
before being proposed.

Your three stated rules are already transcribed and live in
`monitoring/policies/` (01, 02, 03). The two below are extra coverage I noticed
while instrumenting.

---

## 2026-07-25: every started game is eventually completed

**Observes:** `game.completed` (entity `game_id`)
**Why:** catches a game that is started and then abandoned - never won, never
cleaned up. Uses only existing vocabulary, no new instrumentation.
**Caveat (read before adopting):** `has happened` can only *violate* at a
terminal event, and `game.completed` **is** the terminal. So a game that
completes satisfies at completion; a game that is abandoned has no terminal and
stays honestly `pending` until the quiescence TTL reclaims it - it never turns
`violated`. This is a liveness property outside what a finite prefix can
refute; adopt it as a "should eventually" signal, not a hard alarm.

```gherkin
Feature: completeness
  Scenario: every started game is eventually completed
    Then the game is completed has happened
```

## 2026-07-25: an attempt's second card follows a first card

**Observes:** `card.flipped` (entity `game_id, attempt_id`)
**Why:** a well-formed attempt has a first flip and then a second. A stream
carrying a lone "second" flip (no first) is malformed - exactly the shape of a
corrupted/hanging event. This precedence check flags it independently of the
3-second deadline.
**Requires new instrumentation:** one additive step,
`the first card of an attempt is flipped` (a pure predicate on
`slot == "first"`, key `(game_id, attempt_id)`). No change to the game code -
the `card.flipped` event already carries `slot`. If you adopt this, I add the
step to `monitoring/steps.py` and regenerate the catalog.

```gherkin
Feature: well-formed attempts
  Scenario: an attempt's second card follows a first card
    When the second card of an attempt is flipped
    Then the first card of an attempt is flipped before
```
