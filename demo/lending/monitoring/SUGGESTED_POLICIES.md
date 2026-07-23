# Suggested policies

Proposals I (the agent) drafted from the code's observable surface. You own
policies: nothing here is active until you move it into `monitoring/policies/`
and the gates are rerun.

## ADOPTED 2026-07-23: a loan may only be renewed after it was borrowed

Moved to `monitoring/policies/04_renewed_after_borrowed.feature` at the user's
request on 2026-07-23. Now a user-owned policy.

**Observes:** `loan.status` (statuses `renewed`, `borrowed`), key `loan_id`
**Why:** Rule 1 guards *return* against a missing borrow; the same integrity
gap existed for renewal - a renew on a loan that was never borrowed is an
equally impossible state. Caught with the same precedence shape.

```gherkin
Feature: renewal precedence
  Scenario: a loan may only be renewed after it was borrowed
    When a loan is "renewed"
    Then a loan is "borrowed" before
```

## ADOPTED 2026-07-23: a renewed loan is settled again within 21 seconds

Moved to `monitoring/policies/05_renewed_settled_within_21s.feature` at the
user's request on 2026-07-23. Now a user-owned policy.

**Observes:** `loan.status` (statuses `renewed`, `returned`, `lost`), key `loan_id`
**Why:** Rule 3 arms the 21-second deadline at *borrow* only, so a renewal
satisfied it once and the loan was then unbounded. In a real library a renewal
resets the term - a renewed loan should again be acted on within the window.
This re-arms the deadline at each renewal, alongside rule 3 (both hold at once).
