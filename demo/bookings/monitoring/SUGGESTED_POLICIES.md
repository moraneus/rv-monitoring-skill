# Suggested policies

Proposals only. You own the policies - nothing here is active. Move any of
these into `monitoring/policies/` (or tell me to) and I will rerun the gates.

---

## 2026-07-23: A promotion should follow a waitlisting

**Observes:** `booking.status` (promoted, waitlisted), key `booking_id`
**Why:** A booking should only be "promoted" if it was on the waitlist first.
A promotion appearing on a booking that was never waitlisted is a sign the
promotion path fired on the wrong record. Cheap integrity check on the
waitlist-to-reserved transition.

```gherkin
Feature: Promotions follow a waitlisting

  Scenario: a booking is promoted without having been waitlisted
    When a booking is "promoted"
    Then a booking is "waitlisted" before
```

---

## 2026-07-23: A no-show should never be recorded after a cancellation

**Observes:** `booking.status` (cancelled, no_show), key `booking_id`
**Why:** This is the fourth "never" from our interview that you did not pick.
A booking a member actively cancelled should not later be marked as a no_show
(that would wrongly count against the member and misstate attendance). Recorded
here rather than dropped; promote it if you want it watched.

```gherkin
Feature: No no-show after a cancellation

  Scenario: a cancelled booking is later marked no_show
    Given a booking is "cancelled"
    Then a booking is "no_show" never happens
```

---

## Parked: cross-member rules (out of the current fragment)

These are your original wishes (b) and (c). They are **not** expressible in the
per-booking monitor - each requires counting or comparing across many bookings
at once, which the single-entity engine cannot see. They are recorded here as
future work for the day a cross-entity backend is added. In the meantime, the
active policy **"Flagged bookings are never confirmed"**
(`05_flagged_never_confirmed.feature`) is the honest per-booking stand-in: your
app does the counting and stamps a `flag` on the confirmation, and the monitor
enforces that a flagged booking is never confirmed.

- **(b) No member holds two spots in the same class.** Needs: relate all
  bookings sharing a `member_id` + `class_id` and assert at most one active.
  This is a relation across independent entities - out of fragment.
- **(c) A class never exceeds 12 people.** Needs: count active bookings per
  `class_id` against a threshold. This is an aggregate - out of fragment.

Nearest future restatement, once cross-entity is available: re-key on
`class_id` and count, or on `(member_id, class_id)` and assert uniqueness.
