# Suggested policies (proposals - you decide)

These are drafts I thought of while instrumenting the parcel service. Nothing
here is active. To adopt one, move it into `monitoring/policies/` yourself and
re-run the gates. Each below compiles against the current vocabulary and
produces zero violations on the healthy flows.

## 2026-07-25: a delivered parcel is never returned to sender

**Observes:** `parcel.status` (statuses `delivered`, `returned`), key `parcel_id`
**Why:** delivered and returned are meant to be mutually exclusive final
outcomes. This catches a parcel being marked returned-to-sender after it was
already delivered - a data or process error your three rules do not cover.
Like rule 2, it has no terminal event, so its detection window is the
quiescence TTL after delivery.

```gherkin
Feature: mutually exclusive outcomes

  Scenario: a delivered parcel is never returned to sender
    Given a parcel is "delivered"
    Then a parcel is "returned" never happens
```

## 2026-07-25: a re-routed parcel must have been scanned at a hub first

**Observes:** `parcel.status` (statuses `rerouted`, `scanned`), key `parcel_id`
**Why:** a reroute names a hub; a parcel that is rerouted without ever having
been scanned at a hub suggests a phantom/mis-keyed routing event. Decided at
the first reroute (precedence arms once per parcel).

```gherkin
Feature: reroute needs a prior scan

  Scenario: a re-routed parcel must have been scanned at a hub first
    When a parcel is "rerouted"
    Then a parcel is "scanned" before
```

## 2026-07-25: (out of fragment) "every dispatched parcel eventually finishes"

**Why not shipped:** a plain "eventually delivered or returned" (`has happened`)
can only ever reach a `violated` verdict at a terminal event, and this design
deliberately has no terminal event (so rule 2 can keep watching after
delivery). Without a terminal it would pend forever and never alert. Rule 3
already gives you the bounded, always-decidable version of this intent: "…
within 12 seconds." If you want an unbounded eventuality with a real verdict,
that is a modeling change (introduce a terminal event and accept the rule-2
window it opens) - tell me and we will weigh it together.
