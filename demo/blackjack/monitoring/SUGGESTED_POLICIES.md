# Suggested policies

I propose; you dispose. Nothing here is active. To adopt one, move it into
`monitoring/policies/` yourself, then rerun the gates
(`catalog diff` + `replay_check.py`). Each entry below compiles against the
current registry and produces zero violations on the healthy scripted flows.

---

## 2026-07-25: no card after a bust (mirror of rule 1)

**Observes:** `hand.busted`, `hand.dealt` (key `hand_id`)
**Why:** Rule 1 forbids a card after *stand*; the symmetric leak is a card
dealt after a *bust*. A busted hand is final - a further card is as illegal as
one after stand. Catches a dealing bug or tamper that keeps hitting a dead hand.

```gherkin
Feature: a busted hand takes no more cards

  Scenario: a busted hand is never dealt another card
    Given the hand busts
    Then the hand is dealt a card never happens
```

## 2026-07-25: a losing hand is never paid out - PROMOTED

Promoted by the user on 2026-07-25 to
`monitoring/policies/05_losing_hand_not_paid.feature`. No longer a suggestion;
kept here as a record of where it came from.

## 2026-07-25: a busted hand settles promptly

**Observes:** `hand.busted`, `hand.settled` (key `hand_id`)
**Why:** A tighter, bust-specific deadline. A bust is unambiguous - it should
settle almost instantly, so a 5-second bound catches a hand that busts and then
hangs long before the 30-second whole-hand rule (rule 3) would.

```gherkin
Feature: a busted hand settles promptly

  Scenario: a busted hand is settled within 5 seconds
    When the hand busts
    Then the hand is settled within "5" seconds
```

---

## Out of fragment (stated, not approximated)

- **"a hand is never settled/paid twice"** - a *counting* property. The
  tempting `Given the hand is settled / Then the hand is settled never happens`
  transcription self-triggers: the first legitimate settlement opens the scope
  and matches the prohibition in the same tick, so every *first* settlement
  would violate. Genuine duplicate detection needs an app-side guard emitting a
  dedicated `hand.settled_again` marker event, then a self-contained
  `Then ... never happens` on that marker. Say the word and I will instrument it
  (new event + step + a catalog contract change).
- **"the payout equals the bet/winnings"** - a relation between two payload
  fields with arithmetic; the per-entity temporal fragment does not evaluate
  arithmetic across fields. Expressible only by exposing a boolean
  `payout_ok` field at the emit site and forbidding `payout_ok == false`.
