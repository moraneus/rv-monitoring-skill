# The stability workflow: the contract that survives your rewrites

behave-rv's central promise is that policies do not rot silently when code
changes - and as the agent doing the changing, you are the reason this
machinery exists. The committed `monitoring/catalog.json` is a TWO-SIDED
contract: fingerprints of the step predicates (the listener side) and of the
application's `Event(...)` emission sites with their dependency slices (the
shouter side).

## The commands

```bash
# once per intended contract change, committed WITH the change:
python -m behave_rv catalog save \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --app <application .py files>

# after EVERY modification (and in CI):
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies \
  --app <application .py files> --fail-on-app-risk \
  [--trace monitoring/traces/<representative>.jsonl]
```

`--app` takes the application source files/directories that emit events -
keep the list complete; a file left out is a blind spot.

## Reading the diff output

Step side, per `step_id`: `unchanged` / `renamed` (absorbed - renames of
functions, locals, formatting cost nothing) / `changed` or `removed` →
**BREAKS**, listed with a human-readable contract diff and scoped to exactly
the policies whose recorded step identities are affected. An uncompilable
policy is itself reported as a stability failure.

App side, per emission site: `unchanged` / `renamed` (e.g. a class rename -
absorbed) / `behavior-risk` (the emitted interface is intact but code in the
site's dependency slice changed - the named functions/constants tell you
where) / `interface-break` or `removed` (event type, binding keys, payload
keys changed, or the emission is gone) / `added` (new surface, suggestion
material). Risks and breaks are scoped to the policies observing the
affected event types, including deadline policies of the same entity
(event-time coupling - any change to an entity's event flow can move a
deadline verdict). With `--trace`, liveness warnings flag policies whose
event types or bound values never appear in a representative stream - the
net for value renames on the application side.

Renames on the app side, precisely: as of behave-rv 0.3.0 a PURE rename of
any function in an emit slice - including the emitting function itself - is
proven representational by the rename-invariant fingerprint and absorbed as
`renamed`. A rename combined with ANY logic change fails the proof and
flags. Two caveats: a catalog saved by behave-rv < 0.3.0 lacks the proof
field, so renames flag conservatively until the catalog is next
regenerated for an intended change; and renaming a CONSTANT still flags
(names of constants are contract).

## The break protocol (follow exactly)

1. A break or risk you did NOT intend → **stop. Show the user the diff
   output verbatim.** Explain in one sentence per item what moved and which
   policies are at risk. Propose either (a) restoring the contract in code,
   or (b) if the change is genuinely intended, regenerating the catalog.
   Wait for the user on (b). You MAY execute (a) unilaterally - reverting
   the offending edit so the tree stays green while you wait - but then
   your report must state prominently that the requested change is NOT
   applied and is held for the user's decision. Never present a reverted
   request as done.
2. An INTENDED contract change (new event, renamed field the user asked
   for) → make the change, `catalog save`, commit both together, and state
   in your report: "contract change: <what>, catalog regenerated, policies
   affected: <which>". If a policy's phrasing must change too, that is the
   user's call - propose the edit, do not make it. A change is intended
   only when the flagged observable behaviour is ITSELF what the user
   requested; a risk that appears as a side effect of a refactor, cleanup,
   or "no behaviour change" request is unintended by definition - protocol
   1 applies. When in doubt, it is unintended. Always quote the pre-save
   diff verbatim in the report, even for intended changes.
3. Rewording a step phrasing → add the old wording as an alias in the same
   change; verify the diff shows `renamed`, not a break. A `renamed`
   status is absorbed and requires nothing further; you MAY `catalog save`
   afterwards to re-baseline the recorded phrasing so future diffs read
   `unchanged` instead of carrying a permanent `renamed` line - if you do,
   say so in the report. Never fold that re-baseline into the same save as
   an unresolved break.
4. NEVER: hand-edit catalog.json, regenerate it to silence an unintended
   break, or delete a policy to make the diff pass.

## The replay gate

Maintain `monitoring/replay_check.py`: a deterministic scripted traffic run
(fake clock, `tick()` between ordered actions) through the real service and
policies, exiting non-zero on violations, with pinned expected counts. Run
it after the diff on every change - the static side says *may affect*; the
replay says *did*. Update the pinned expectations only when behaviour
intentionally changed, and say so.

## CI

Ship this job in the project (template: `templates/monitoring/ci-snippet.yml`
next to this skill): install the package, run `catalog diff` with
`--fail-on-app-risk`, run `replay_check.py`. Exit codes gate the merge. The
live dashboard shows the same contract state at runtime when constructed
with `registry=`, `catalog=`, and `app=`.
