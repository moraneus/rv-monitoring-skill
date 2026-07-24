# Suggested policies (proposals - you decide what becomes a policy)

The four rules you stated are already transcribed into `monitoring/policies/`.
Everything below is something *I* thought of while instrumenting the game; none
of it is active. If you want one, tell me and I will move it into
`policies/` and re-run the gates. Each draft compiles against the current
vocabulary.

## 2026-07-25: a hand is never settled twice - PROMOTED (now a policy)

You promoted this. Note the original draft here (`Given the hand is settled /
Then the hand is settled never happens`) was **defective**: the scope-opener
and the prohibition were the same event, so it fired on every hand's first
legitimate settlement, and "at most one settlement" is a counting property
outside the fragment. It shipped instead via additive instrumentation: the
game emits `hand.resettled` on the re-settlement guard path, and the live
policy is the self-contained `never` in
`policies/05_no_double_settlement.feature`:

```gherkin
Feature: no double settlement
  Scenario: a hand is never settled twice
    Then a hand is resettled never happens
```

Boundary you accepted: a raw stream-duplicate of `hand.settled` that never
passes through the settle guard is not caught (no single-occurrence rule can);
the marker guards the real re-settlement path through the game code.

## 2026-07-25: a winning hand is paid within 5 seconds

**Observes:** `hand.settled` (outcome=win), `hand.payout`
**Why:** Your rule 4 forbids paying *before* settlement; it does not require
that a win is *ever* paid. This bounded-response rule catches a win that
settles and then never pays out (a stuck or dropped payout). Pick a bound that
fits the table; 5 seconds is a placeholder.

```gherkin
Feature: a winning hand is paid
  Scenario: a winning hand is paid within 5 seconds
    When the hand is settled as a "win"
    Then a payout happens within "5" seconds
```

## 2026-07-25: a card is only dealt after the hand is dealt

**Observes:** `hand.dealt`, `hand.card`
**Why:** A sanity ordering rule: a card event for a hand that was never opened
by `hand.dealt` means a corrupted or mis-keyed emission. Cheap ordering guard
on the lifecycle start.

```gherkin
Feature: cards follow the deal
  Scenario: a card is only dealt after the hand is dealt
    When a card is dealt to the "player"
    Then a hand is dealt before
```
