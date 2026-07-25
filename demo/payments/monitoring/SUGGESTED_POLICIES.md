# Suggested policies (proposals - you decide what becomes a policy)

I propose; you dispose. Nothing here is active. Your three rules live in
`policies/`. This file holds new coverage you don't have yet.

---

## Resolved: the rule-1 / rule-2 conflict (for the record)

Earlier, rules 1 and 2 as first stated jointly forbade the lifecycles you
described (a disputed payment had no legal exit), and the replay gate was RED.
You resolved both, and the changes are now shipped in `policies/`:

- **Rule 1** narrowed to "no new charge activity (re-authorize / re-capture)
  after a dispute"; the team's investigate / refund / close is exempt.
- **Rule 2** scoped to *disputed* closes via an app-side marker
  (`payment.dispute_closed`); a plain close is free.

Both described healthy flows now run clean in `replay_check.py` and the demo.

---

## New coverage you don't have yet

### A frozen rejection only happens to an already-disputed payment

**Observes:** `payment.rejected` (frozen), `payment.status` (disputed)
**Why:** a "frozen" rejection should only ever be issued once a payment is
actually in dispute; one issued earlier is a bug in the freeze guard. This
watches the guard rule 1 now relies on for post-close protection.

```gherkin
Feature: frozen rejections are well-formed

  Scenario: a frozen rejection is only issued after a dispute
    When a payment is frozen-rejected
    Then a payment is "disputed" before
```

### A payment is captured only after it was authorized

**Observes:** `payment.status` (captured, authorized)
**Why:** capture without a prior authorization is a broken lifecycle; cheap
precedence check, clean on every described flow.

```gherkin
Feature: capture follows authorization

  Scenario: a payment is captured only after it was authorized
    When a payment is "captured"
    Then a payment is "authorized" before
```
