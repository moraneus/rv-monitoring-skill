# Suggested policies (proposals only)

You own the policies. These are proposals; nothing here is active until you
move it into `monitoring/policies/` yourself. Each has been verified to compile
against the current registry. Active in `policies/`: the three laws you stated
(strict alternation, no move after finish, every game finishes) plus
**"a move only happens after its game has started"**, which you promoted from
this file on 2026-07-25 (moved to `04_move_after_start.feature`).

---

## 2026-07-25: a game never finishes before any move is made

**Observes:** `game.status` (finished), `game.move`
**Why:** guards the *other* boundary of the lifecycle. Law 2 forbids a move
after the finish; this forbids a finish with no move before it, i.e. a
corrupted or premature `won`/`draw` on an empty board.

```gherkin
Feature: finish only after play

  Scenario: a game never finishes before any move is made
    When a game is finished
    Then a move is made before
```

---

## Out of fragment (stated honestly, not proposed)

These are real properties of tic-tac-toe that the single-entity temporal
fragment cannot express, so they are **not** offered as policies:

- **"the same cell is never played twice"** -- relates two move events by their
  `cell` value (a relation/counting over the entity's own history). The
  fragment's predicates are single-event; it cannot compare one move's cell to
  another's. Enforce this in the game logic (the service already does) rather
  than in a policy.
- **"X and O each make at most 5 / 4 moves"** -- counting, out of fragment.
- **"the winner occupies a full line"** -- would need the `won` event to carry
  the winning line and a predicate over it; expressible only by exposing that
  field, and even then it is a property of one event, not a temporal rule.
