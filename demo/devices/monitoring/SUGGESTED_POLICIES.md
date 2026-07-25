# Suggested policies (proposals only)

These are behave-rv agent proposals for monitorable behaviour the current
event vocabulary already exposes but no committed policy covers. **You own the
policies** - nothing here is active. Move an entry into
`monitoring/policies/` yourself if you want it, then I will rerun the gates.

---

## Adopted

- **an action is only ever performed by an activated device** - adopted
  2026-07-25 as `policies/05_action_only_after_activation.feature`.
- **a device is only quarantined after it was activated** - adopted
  2026-07-25 as `policies/06_quarantine_only_after_activation.feature`.

---

## Out of fragment (mentioned, not proposed)

- **"a wiped device must eventually be retired"** is an unbounded-liveness
  requirement. As `Then a device is "retired" has happened` it can only reach
  a `violated` verdict at a terminal event, and a device that is wiped but
  then abandoned never emits one - so it would pend forever and never catch
  the very case you would care about. Out of the monitorable fragment as
  stated. The nearest in-fragment property is a bounded one:
  *"a wiped device is retired within N seconds"* (`When a device is "wiped"` /
  `Then a device is "retired" within "<n>" seconds`). Tell me the deadline and
  I will propose it.
