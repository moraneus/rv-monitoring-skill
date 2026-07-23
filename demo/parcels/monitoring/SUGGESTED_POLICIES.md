# Suggested policies (proposals - you decide)

These are monitorable behaviours the instrumentation now exposes but your
three rules do not cover. They are proposals only: nothing here is active
until you move it into `monitoring/policies/` yourself. Each compiles against
the current vocabulary (`monitoring/STEPS.md`).

## 2026-07-23: registration precedes hub scan

**Observes:** `parcel.status` (statuses `scanned`, `registered`), key `parcel_id`
**Why:** A hub scan for a parcel the service never registered is a lost or
mis-keyed parcel - the same class of gap rule 1 guards one step later in the
lifecycle. Catches events arriving for unknown parcels.

```gherkin
Feature: registration precedes scanning

  Scenario: a parcel must be registered before it is scanned at a hub
    When the parcel becomes "scanned"
    Then the parcel becomes "registered" before
```

## 2026-07-23: returned parcels are never delivered

**Observes:** `parcel.status` (statuses `returned`, `delivered`), key `parcel_id`
**Why:** The mirror image of rule 2. Rule 2 forbids a reroute after delivery;
this forbids the other contradictory terminal transition - a parcel marked
returned-to-sender must never later be marked delivered. Together they pin
both final states as truly final.

```gherkin
Feature: returned parcels are never delivered

  Scenario: once a parcel is returned to sender it must never be marked delivered
    Given the parcel becomes "returned"
    Then the parcel becomes "delivered" never happens
```
