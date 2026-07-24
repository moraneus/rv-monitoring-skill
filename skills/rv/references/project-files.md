# The monitoring/ directory: what you create and maintain

```
monitoring/
  steps.py                 # the vocabulary module
  policies/                # USER-OWNED .feature files
    01_<policy>.feature
  catalog.json             # generated contract (catalog save), committed
  STEPS.md                 # GENERATED vocabulary doc - regenerate, never edit
  SUGGESTED_POLICIES.md    # your proposals (see policy-authoring.md)
  generate_steps_doc.py    # STEPS.md generator (from the skill's templates)
  replay_check.py          # deterministic verdict gate (exit-coded)
  traces/                  # recorded .jsonl streams (TraceRecorder / record_events)
```

Bootstrap from the `templates/monitoring/` directory shipped next to this
skill, replacing the `__PLACEHOLDER__` markers; then `pip install behave-rv`
and run the gates once to produce the initial `catalog.json`.

## steps.py rules

- `build_registry() -> StepRegistry` factory, side-effect-free at import
  (the CLI detects and uses it), plus `load_policies(registry)` compiling
  every `.feature` under `policies/` in sorted order.
- `step_id` naming: `<domain>.<event>.<what>` (`order.status.is`). Stable
  forever; never reused for a different meaning.
- Predicates are pure: read the event, return a boolean. The placeholder
  names in the phrasing must match the parameter names (call-by-name).
- One step per *condition*, not per event type - several steps may observe
  the same event type reading different fields.

## STEPS.md - the user's authoring surface

After ANY change to `steps.py`, run:

```bash
python monitoring/generate_steps_doc.py
```

It renders, from the live registry: every phrasing and alias, its
parameters, the event type and correlation key it observes, and ready-to-copy
example scenarios for each applicable temporal form. This file is how the
user writes policies without reading Python - keeping it complete and fresh
is part of the definition of done for every change. It is generated so it
cannot drift; treat a hand edit to it as a bug.

## Definition of done, per change

1. Code instrumented per the conventions.
2. `steps.py` covers the new observable behaviour; aliases preserved on any
   rewording.
3. `STEPS.md` regenerated.
4. New uncovered behaviour proposed in `SUGGESTED_POLICIES.md`.
5. `catalog diff --app --fail-on-app-risk` clean, or breaks reported to the
   user; `catalog save` only for intended contract changes, committed
   together.
6. `replay_check.py` green (expectations updated only for intended
   behaviour changes, stated in the report). The scripted traffic MUST
   include every normal flow the user described, and those healthy flows
   must produce ZERO violations - a violation on a described healthy flow
   is a rule conflict to surface with options (see the joint-satisfiability
   rule in policy-authoring.md), never a count to accept into the pins.
7. Traces refreshed if the event vocabulary grew (`--trace` liveness stays
   meaningful only on representative streams).
8. If the change touched a live entry point: the dashboard is wired
   (`Dashboard(policies, registry=, catalog=, app=)`, events tapped,
   verdicts sinked) and the report's "Live view" line gives the user the
   URL.
