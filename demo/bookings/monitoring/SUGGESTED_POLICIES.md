# Suggested policies (proposals - you own the decision)

These are drafts the agent proposes. Nothing here is active. Move one into
`monitoring/policies/` only if you want it, and the gates will re-run.
Each draft below has been checked to compile against the current vocabulary.

---

## 2026-07-23: Turn "every booking resolves" into a real alarm (deferred by you)

**Observes:** `booking.status` (reserved, and the final states)
**Why:** Your policy 06 (`every booking eventually reaches a final state`) can
only ever read *satisfied* or *still-waiting* - it never becomes a hard alarm,
because "eventually" has no deadline. If you ever want a booking left in
`reserved`/`waitlisted` too long to actually page you, give it a deadline and
it becomes a timer-fired violation. You said skip this for now; recorded so it
is not lost. Pick `<N>` (e.g. class start plus a grace window).

```gherkin
Feature: resolution deadline

  Scenario: every booking reaches a final state within the window
    When a booking is "reserved"
    Then a booking reaches a final state within "3600" seconds
```

---

## 2026-07-23: No member confirmed twice into the same class (partial)

**Observes:** `seat.confirmed` (already emitted at every confirmation), keyed
by the (member, class) pair
**Why:** This is the closest in-fragment take on your wish "no member should
hold two spots in the same class". By treating each (member, class) pair as one
entity, a *second* confirmation for the same pair is a per-entity violation -
no counting required. Honest limits: it catches a double **confirmation**, not
two simultaneous *holds* (a reserve + a waitlist), and it says nothing about
the class total. The `seat.confirmed` event already exists, so adopting this is
just moving the policy in.

```gherkin
Feature: no double booking in a class

  Scenario: a member is confirmed in a class at most once
    Given a seat is "confirmed"
    Then a seat is "confirmed" never happens
```

---

## 2026-07-23: A booking is only promoted after it was waitlisted

**Observes:** `booking.status` (waitlisted, promoted)
**Why:** The second half of the ordering guards - promotion should only follow
a waitlist. Cheap hardening against a promotion appearing from nowhere. You
kept the first half (`attended` only after `checked_in`) as policy 05 and left
this one as a suggestion.

```gherkin
Feature: promotion ordering

  Scenario: a booking is only promoted after it was waitlisted
    When a booking is "promoted"
    Then a booking is "waitlisted" before
```

---

## Out of fragment - recorded, not approximated

These need counting across many bookings, which the per-booking engine cannot
express. They are kept here as future-fragment material (they would need a
first-order/relational backend, not this one). Nothing above is a substitute
for them - the double-booking suggestion S2 covers only the double-confirm
slice.

- **A class never goes over 12 people.** A capacity aggregate: it counts
  confirmed bookings per class and compares to a limit. No honest per-booking
  rewrite exists.
- **No member holds two active spots in the same class (full sense).** Counts a
  member's simultaneous holds (reserve + waitlist + promote) within a class.
  S2 above covers only the double *confirmation* case.
