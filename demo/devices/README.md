# IoT fleet tracker with embedded runtime verification

A small fleet tracker instrumented with [behave-rv](https://github.com/moraneus/behave-rv).
Devices are provisioned, their provision check passes or fails, they are
activated, perform actions, may be quarantined, wiped, and finally retired
(retirement ends a device). Sensor feeds are a separate entity: each pushes
readings carrying a status.

## Layout

```
app/
  fleet.py     # the service (business logic), instrumented with Event(...)
  demo.py      # LIVE run: dashboard + scripted healthy and violating traffic
monitoring/
  steps.py                 # the policy vocabulary (pure predicates)
  policies/                # the four rules, as Gherkin (user-owned)
  catalog.json             # generated two-sided stability contract (committed)
  STEPS.md                 # generated vocabulary doc
  SUGGESTED_POLICIES.md    # agent proposals (not active)
  replay_check.py          # deterministic verdict gate (exit-coded)
  generate_steps_doc.py    # regenerates STEPS.md
  traces/                  # recorded event streams
```

## The policies (in `monitoring/policies/`)

Rules 1-4 are the user's original requirements; rules 5-6 were agent
suggestions the user adopted.

1. **Activation immediately after provision-ok** - `previously`: the event
   right before `activated` must be `provision_ok`.
2. **Quarantine containment** - scoped `never`: once `quarantined`, no
   non-blocked action may occur. Observes `device.action` only, so
   decommissioning (wipe, retire) is not an "action" and is permitted.
3. **Retirement safety** - `before`: a `retired` device must have been
   `wiped` at some earlier point.
4. **Sensor feed health** - `always holds`: every reading on a sensor feed is
   status `ok`.
5. **Action readiness** - `before`: a device's first `ok` action must be
   preceded by `activated`.
6. **Quarantine readiness** - `before`: a device is only `quarantined` after
   it was `activated`.

## Run it

```bash
python app/demo.py                 # live dashboard on http://127.0.0.1:7204
python monitoring/replay_check.py  # batch gate: exit 1 on unexpected verdicts
```

The dashboard shows each policy as a card with per-entity verdicts, the
rendered explanation for every violation, the live event feed, and the
stability strip (are the step contracts and the app's emit sites still
matching `catalog.json`).
