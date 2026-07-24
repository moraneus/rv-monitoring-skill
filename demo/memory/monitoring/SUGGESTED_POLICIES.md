# Suggested policies (proposals - you decide)

These are my proposals for extra coverage the current vocabulary already
supports. None is committed. Move any you want into `monitoring/policies/`
yourself, then rerun the gates. Each has been checked to compile against the
current registry.

Your rules now live in `monitoring/policies/`:
1. a matched card is never flipped again
2. a pending attempt resolves within three seconds
3. nothing happens after the game is complete
4. every matched card was flipped first  *(promoted from a suggestion on
   2026-07-25 - a match out of nowhere is stream corruption you want caught)*

---

## 2026-07-25: no attempt resolves without becoming ready

**Observes:** `attempt.resolved`, `attempt.pending` (key `attempt_id`)
**Why:** Every resolution should correspond to an attempt that actually became
ready (its second card was flipped). Guards against a stray or duplicated
`attempt.resolved` with no matching `attempt.pending`.

```gherkin
Feature: attempt integrity
  Scenario: no attempt resolves without becoming ready
    When an attempt is resolved
    Then an attempt is ready before
```

## 2026-07-25: a completed game is never restarted

**Observes:** `game.complete`, `game.start` (key `game_id`)
**Why:** Once a game is complete its id is done; a second `game.start` for the
same id would mean id reuse. Complements rule 3 (which forbids `game.action`
after completion) by forbidding a fresh lifecycle start too.

```gherkin
Feature: lifecycle integrity
  Scenario: a completed game is never restarted
    Given the game is complete
    Then the game starts never happens
```

---

## Out of fragment (stated, not approximated)

- **"a card belongs to exactly one attempt"** relates a card to an attempt -
  two independent correlation keys in one rule. The fragment is one key per
  scenario, so this cannot be expressed directly. The nearest in-fragment
  check is the per-card "flipped before matched" above.
- **"no more than N attempts before completion"** is a count/aggregate over an
  entity, outside the temporal fragment. Verdicts over the recorded stream
  (counting `attempt.pending` per game offline) are the honest way to get it.
