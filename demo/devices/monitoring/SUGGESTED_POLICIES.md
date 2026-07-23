# Suggested policies

These are proposals only. Nothing here is monitored until you move it into
`monitoring/policies/` yourself. Each entry compiles against the current
registry.

## 2026-07-23: a device must have been provisioned before activation

**Observes:** `device.status` (provisioned, activated), key `device_id`
**Why:** Rule 1 checks the *immediate* predecessor of activation is a passed
check (`previously`). It does not catch a device that was never provisioned at
all if some other event happens to sit right before activation. This `before`
companion asserts a provisioning event exists somewhere in the device's past,
closing that gap.

```gherkin
Feature: activation prerequisite
  Scenario: a device must have been provisioned before it is activated
    When a device is "activated"
    Then a device is "provisioned" before
```

## 2026-07-23: a wiped device is never activated again

**Observes:** `device.status` (wiped, activated), key `device_id`
**Why:** A wipe is a decommissioning step. Re-activating a wiped device (reusing
a device that was meant to be torn down) is a likely fleet-management bug and a
security concern. This scoped `never` latches at the first wipe and forbids any
later activation for that device.
Caveat: if your fleet legitimately re-commissions a wiped device under the same
`device_id`, this would flag it - decide whether that flow is intended before
adopting.

```gherkin
Feature: no reuse after wipe
  Scenario: a wiped device is never activated again
    Given a device is "wiped"
    Then a device is "activated" never happens
```

## 2026-07-23: OUT OF FRAGMENT - "more than 3 devices in quarantine at once"

**Status: ACCEPTED (2026-07-23).** You chose the app-side-counting approximation
below and made the policy yours. It now lives at
`monitoring/policies/05_quarantine_surge.feature`; the counting and surge event
are instrumented in `FleetService`, and the `a quarantine surge is flagged` step
is in the registry. The caveat in this entry (the "more than 3" threshold lives
in the application, not the engine) is the design you accepted. Kept here as the
record of the decision. Original analysis follows.

The rule as you originally stated it CANNOT be monitored by the engine as a
count across devices. Here is why, and the approximation you adopted.

**Why it is out of fragment.** behave-rv's engine is a per-entity monitor: one
scenario compiles to one independent state machine *per correlation key value*,
and the fragment has no operator that counts or relates across different
entities. "More than 3 devices" is a count over the whole device *population*,
and "at the same time" is a concurrency condition across those separate
`device_id` monitors. There is no per-device restatement of it - no single
device's own event history tells you how many *other* devices are quarantined.
Counting and cross-entity aggregation are exactly what the fragment refuses, on
purpose: it is the price of a deterministic, per-key engine. I will not fake it
with a per-device policy that looks like it checks this but does not.

**Nearest in-fragment approximation (requires new instrumentation - your call).**
Move the counting to the application (the "shouter" side), where it is allowed,
and let the engine verify the *result* deterministically:

1. `FleetService` keeps a live set of currently-quarantined devices: add on
   `quarantine`, remove on `wipe` and `retire` (a wiped/retired device is no
   longer quarantined). This is additive - it does not reshape existing logic.
2. When that count crosses above 3, emit a NEW fleet-keyed event:
   `Event("fleet.quarantine", clock(), {"fleet_id": "fleet"}, {"level": "surge"},
   "fleet-tracker")` (a singleton `fleet_id`). Optionally emit `{"level": "clear"}`
   when it drops back to 3 or fewer.
3. Add one step to `monitoring/steps.py`:
   `a quarantine surge is flagged` -> `fleet.quarantine.surge`, event
   `fleet.quarantine`, key `fleet_id`.
4. The alerting policy (verified to compile against that step):

```gherkin
Feature: quarantine surge alert
  Scenario: no more than 3 devices are quarantined at once
    Then a quarantine surge is flagged never happens
```

It goes `violated` the instant the app emits a surge - that violation IS your
alert, delivered through the same dashboard, sink, and explanation path as every
other policy.

**The honest caveat you are accepting if you adopt this:** the "more than 3"
threshold logic lives in the application code, NOT in the deterministic engine.
The engine only verifies that a surge event, once emitted, is reported - it does
not itself count devices. That moves a piece of the specification into the
shouter side (a new event surface you would be trusting the app to compute
correctly, and which the stability catalog would then track). If you want the
counting itself to be engine-owned and deterministic across entities, that needs
the first-order / multi-entity backend behave-rv leaves a slot for - not the
current single-key engine. Tell me which way you want to go and I will wire it.
