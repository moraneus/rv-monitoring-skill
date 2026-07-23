# Suggested policies (proposals - you decide what becomes a policy)

The four rules you stated are already transcribed into `monitoring/policies/`
as user-authored policies. The items below are extra coverage I noticed while
instrumenting; none is committed. Each compiles against the current registry.

## ACCEPTED (moved to policies/): fleet-wide quarantine surge

The "alert when >3 devices are quarantined at once" rule was out of fragment as
literally stated (cross-entity counting). You accepted the key-projection
reformulation: the application counts concurrent quarantines (`FleetCounter` in
`app/service.py`) and emits a singleton `fleet.quarantine` "surge" event on the
upward crossing; the policy turns that surge into the alert. It now lives in
`monitoring/policies/05_fleet_quarantine_surge.feature` as your policy, with the
step `the fleet quarantine level is "{level}"` and the new event fingerprinted
into the catalog. It is single-shot per fleet (first surge alerts, then
settles), which you accepted.

## 2026-07-23: a device is only activated after it was provisioned

**Observes:** `device.status` (device_id)
**Why:** rule 1 pins activation to the *immediate* predecessor (`previously`).
A weaker companion catches a device that is activated having never been
provisioned at all - useful if a future refactor can emit `activated` for an
unknown device. `before` fires on any missing precedent, not just an
out-of-order one.

```gherkin
Feature: device provisioning precedence

  Scenario: a device is only activated after it was provisioned
    When a device is "activated"
    Then a device is "provisioned" before
```

## 2026-07-23: a wiped device is never acted on again

**Observes:** `device.status` (device_id)
**Why:** a wipe is meant to be final before retirement; an `acted` event after
a `wipe` would mean the device kept working post-wipe. Scoped `never` catches
that without touching rule 3.

```gherkin
Feature: post-wipe containment

  Scenario: a wiped device performs no further actions
    Given a device is "wiped"
    Then a device is "acted" never happens
```

## 2026-07-23: a sensor feed eventually reports at least one reading

**Observes:** `sensor.reading` (sensor_id)
**Why:** rule 4 says every reading must be ok, but a feed that goes silent
(emits nothing) satisfies it vacuously. This flags a provisioned feed that
never reports. NOTE: needs a terminal event for sensors to ever produce a
`violated` verdict - sensors currently have none, so this would sit `pending`
on a live stream. Offered only if you want to add a `sensor.closed` terminal.

```gherkin
Feature: sensor liveness

  Scenario: a sensor feed reports at least one reading
    Then a sensor reading is "ok" has happened
```
