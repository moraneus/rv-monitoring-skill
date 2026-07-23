# Suggested policies (proposals - you decide what becomes a policy)

These are drafted by the coding agent from the monitorable surface. None is
active. To adopt one, move its `.feature` into `monitoring/policies/` yourself
and rerun the gates. Each below compiles against the current registry.

## 2026-07-23: a parcel is out for delivery before it is delivered

**Observes:** `parcel.status` (statuses `out_for_delivery`, `delivered`); key `parcel_id`
**Why:** catches a "delivered" event for a parcel that never went out for
delivery - a phantom delivery or a mis-sequenced status update. Complements
rule 1 (which guards the hub scan) by guarding the step just before delivery.

```gherkin
Feature: no phantom deliveries
  Scenario: a parcel is out for delivery before it is delivered
    When a parcel is "delivered"
    Then a parcel is "out_for_delivery" before
```

## 2026-07-23: a parcel is registered before it is scanned at a hub

**Observes:** `parcel.status` (statuses `registered`, `scanned`); key `parcel_id`
**Why:** a scan for a parcel the service never registered signals a lost or
out-of-order registration event - the lifecycle should always start at
`registered`.

```gherkin
Feature: registration precedes scanning
  Scenario: a parcel is registered before it is scanned at a hub
    When a parcel is "scanned"
    Then a parcel is "registered" before
```

## 2026-07-23: a scanned parcel goes out for delivery within 20 seconds

**Observes:** `parcel.status` (statuses `scanned`, `out_for_delivery`); key `parcel_id`
**Why:** an SLA on hub dwell time. A parcel scanned at a hub but not dispatched
within the window is stuck. Demo-scale duration (20s); pick the real value.
Note: this is a proposal, not one of your three stated rules - the number is a
placeholder for you to set.

```gherkin
Feature: hub handover SLA
  Scenario: a scanned parcel goes out for delivery within 20 seconds
    When a parcel is "scanned"
    Then a parcel is "out_for_delivery" within "20" seconds
```
