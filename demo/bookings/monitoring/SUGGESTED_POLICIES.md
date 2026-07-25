# Suggested policies (proposals - you own the decision)

These are mine to propose, yours to accept or reject. Nothing here is active;
active policies live in `policies/`. When you want one, tell me and I'll move
it in and rerun the gates.

---

## 2026-07-25: double-holding - a member's second spot in the same class

**Status:** out of fragment as stated; recorded as a future wish (parked for later).

**Why:** "no member holds two spots in the same class" relates two different
bookings to each other and to a member - counting across entities, which a
per-booking monitor cannot do. The honest in-reach version is the same trick
we used for the capacity cap: your booking code already knows when a member is
grabbing a second spot in a class it can see, so it emits a booking-keyed
marker and the monitor makes it loud.

**Observes (if built):** a new `booking.duplicate_hold` marker event, keyed by
`booking_id`, emitted by the app at the booking site when it detects the
member already holds a spot in that class; plus one new step
`a booking duplicates the member's spot`.

```gherkin
Feature: one spot per member per class
  Scenario: a booking never duplicates the member's existing spot
    Then a booking duplicates the member's spot never happens
```

Cost: one new event type + one new step + a catalog contract change. Say the
word and I'll build it exactly like the capacity rule.

---

## 2026-07-25: the softer orderings you didn't ask to alarm on

**Status:** available if you want them; these are how bookings normally flow,
where alarms are not required. Parked here so the option is visible.

**Why:** they catch a booking that skipped a normal step - useful if you ever
suspect the flow itself is being bypassed, not just its endpoints.

```gherkin
Feature: normal booking order
  Scenario: a booking is only confirmed after it was reserved or promoted
    When a booking is "confirmed"
    Then a booking is "reserved" before

  Scenario: a booking is only promoted after it was waitlisted
    When a booking is "promoted"
    Then a booking is "waitlisted" before
```

Note: `before` is any-earlier-event precedence, so "reserved or promoted
before confirmed" is best expressed as the reserved-before form (every
promoted booking was reserved first anyway). If you want these, I'll confirm
the exact reading with you before moving them in.

---

## 2026-07-25: consider making the capacity rule LOUD

**Status:** a knob, not a policy. Rule 07 (class over capacity) currently just
logs. You listed only cancel-then-checkin and the 15s promotion deadline as
paging. A cap slip is arguably page-worthy too - one word from you and I add it
to the loud set in the live monitor.
