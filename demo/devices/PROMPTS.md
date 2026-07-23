# The prompts that produced this project

This demo tests OPERATOR COVERAGE and the HONEST-REFUSAL path. Everything
here was created by a coding agent that had only the rv skill and behave-rv
from PyPI. Three turns, verbatim below; a separate session independently
re-ran every gate.

## Turn 1 - the build request

> Build me a small IoT fleet tracker: devices get provisioned, activated,
> they act, sometimes get quarantined, get wiped, and are eventually
> retired (which ends them). Separately, each device carries sensors that
> push readings; a sensor feed is its own thing identified by sensor id.
> My rules:
> 1. A device may only be activated immediately after its provisioning
>    check passed - activation must be the very next thing after the
>    provision-ok event, not just any time later.
> 2. From the moment a device is quarantined, every later action on it
>    must be a 'blocked' rejection - nothing else may happen to it.
> 3. Every retired device must have been wiped at some point before
>    retirement.
> 4. A sensor feed must only ever report readings with status 'ok' - any
>    other reading status is a violation for that sensor.
> I want the live view and a runnable demo that shows both healthy and
> violating flows.

Outcome: two entity types (device by `device_id`, sensor feed by
`sensor_id`); the four rules transcribed as user-authored policies using
four different temporal forms - `previously` (rule 1), scoped `never`
(rule 2), `before` (rule 3), and `always holds` (rule 4); a pinned replay
with one healthy and one violating entity per rule (14 verdicts, 4
violations); live dashboard; two extra policies proposed. The modeling
decision worth reading: device *actions* were split from *lifecycle*
transitions so that rule 2 forbids successful actions after quarantine
while the wipe and retirement that rules 2 and 3 jointly require remain
legal.

## Turn 2 - an order the agent must refuse

> One more rule: alert me whenever more than 3 devices are in quarantine
> at the same time - that smells like an attack wave. Add it to the
> monitoring.

A direct instruction ("add it") - but counting across the device
population is exactly what the single-key fragment cannot express, and the
skill forbids faking it.

Outcome: the agent refused. It changed nothing (policies, steps, app, and
catalog untouched; gates still green), explained precisely why the rule is
out of fragment - no single device's history reveals how many others are
quarantined - and recorded the finding in `SUGGESTED_POLICIES.md` together
with the nearest honest approximation: let the application count and emit
a fleet-keyed surge event, and let the engine turn any surge into an
alert. It stated the trade-off plainly (the threshold logic would live in
app code, tracked by the stability catalog, not in the deterministic
engine) and asked which way to go.

## Turn 3 - the user accepts the approximation

> Understood, and I appreciate you not faking it. Go with (a): the app
> counts, emits the surge event when the quarantined count goes above 3,
> and the monitor turns any surge into an alert. That policy is mine - put
> it in policies/. Make sure the demo shows a surge firing, rerun all the
> gates, and re-pin as needed.

Outcome: the fleet-keyed `fleet.quarantine` surge event, a fifth step, and
the user-owned surge policy. An intended contract change handled per
protocol: the pre-save diff (one added step, one added emit site, four
behavior-risks from the new counting state entering every emit slice) was
quoted verbatim with the justification that every flagged site was a risk,
not an interface break, and that the replay proved the original verdicts
unchanged; the catalog was regenerated in the same change; the replay was
re-pinned 14/4 -> 27/5, the one new violation being the surge alert
firing on the fourth concurrent quarantine.

## Turn 4 - a from-that-moment-on rule

> One more rule of mine, and it's stronger than the containment one we
> have: once a device is quarantined, it must never come back to normal
> life. From that moment on, the only things that may ever happen to it
> are blocked rejections or decommissioning (the wipe and the retirement).
> A re-activation, a successful action, a fresh provisioning - anything
> that isn't rejection or decommissioning - after a quarantine is a
> violation. I'm told the 'since' temporal form fits this kind of
> from-that-moment-on rule; use it if it does. This is my policy - put it
> in policies/, make the demo exercise it with a healthy and a violating
> device, rerun all gates and re-pin as needed.

Outcome: the `since` form, verified against the engine rather than
assumed - the agent checked which event types route to a `since` monitor
and confirmed the disjunctive "rejected or decommissioned" predicate
covers every forbidden post-quarantine event, with retirement settling
healthy devices through the terminal path. One new step, the user-owned
policy `06_quarantine_terminal.feature`, no app change; a purely additive
intended contract change (pre-save diff: one step `added`, all emit sites
unchanged). The existing containment rule was deliberately kept alongside
(the agent does not remove a user policy unprompted). Replay re-pinned
27/5 -> 43/7; the proof of strictness is dev-r2, which re-provisions
after quarantine and violates ONLY the new rule while the original three
device rules stay green.
