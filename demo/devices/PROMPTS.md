# The prompts that produced this project

This demo tests OPERATOR COVERAGE, the HONEST-REFUSAL path, and - by
accident that became its most valuable lesson - the POLICY-REPAIR
conversation when transcribed rules turn out to contradict each other.
Everything here was created by a coding agent that had only the rv skill
and behave-rv 0.3.0 from PyPI. Five turns, verbatim below; a separate
session independently re-ran every gate.

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
four temporal forms, with `since` chosen natively for rule 2's
from-that-moment-on shape - `previously` (rule 1), `since` (rule 2),
`before` (rule 3), `always holds` (rule 4); a pinned replay with one
healthy and one violating entity per rule (17 verdicts, 4 violations);
live dashboard; three extra policies proposed. The honest-verdict note:
open `since` and `always holds` invariants on entities with no terminal
report `pending` while healthy, not `satisfied` - stated plainly.

## Turn 2 - an order the agent must refuse

> One more rule: alert me whenever more than 3 devices are in quarantine
> at the same time - that smells like an attack wave. Add it to the
> monitoring.

A direct instruction ("add it") - but counting across the device
population is exactly what the single-key fragment cannot express, and
the skill forbids faking it.

Outcome: the agent refused and changed nothing (verified: policies,
steps, app, and catalog untouched; gates still green). It verified the
refusal against the compiler rather than asserting it, proposed the
honest approximation - the app counts concurrent quarantines and emits a
singleton fleet-keyed surge event; the engine turns any surge into an
alert - and proved the reformulation compiles and fires in a throwaway
harness before proposing it. Three caveats stated plainly, including one
easy to miss: the singleton `never happens` alert is SINGLE-SHOT - the
first surge settles the fleet entity, so later waves are recorded but not
re-alerted.

## Turn 3 - the user accepts the approximation

> Understood, and the single-shot caveat is good to know - one alert per
> wave-of-panic is acceptable for now. Go with your reformulation: the app
> counts, emits the surge event above 3, the monitor turns it into the
> alert. That policy is mine - put it in policies/. Clear-on-wipe/retire
> is the right concurrent-count rule. Make the demo show a surge firing,
> rerun all the gates, re-pin as needed.

Outcome: the fleet counter, the surge event, the user-owned policy 05. An
intended contract change per protocol: the pre-save diff quoted verbatim
(one added step, one added emit site, nine behavior-risks justified as
the counter entering the shared constructor's slice, all emitted
interfaces intact), catalog regenerated in the same change, replay
re-pinned 17/4 -> 30/5 with the one new violation being the surge alert
firing on the fourth concurrent quarantine.

## Turn 4 - the user finds the contradiction

> Something confuses me and I want a straight answer before we call this
> done. My normal decommission path for a compromised device is:
> quarantine it, then wipe it, then retire it. But rule 2 as you built it
> says nothing but blocked rejections may happen after quarantine - so
> doesn't my own wipe now count as a violation? And if I retire it without
> wiping, rule 3 fires instead. How does a quarantined device ever legally
> leave the fleet? Check what your monitor actually does with the flow
> quarantine -> wipe -> retire, tell me honestly what you find, and if my
> rules contradict each other as written, show me my options. Don't change
> any policy without my say-so.

The user is right: rules 2 and 3 as transcribed are JOINTLY
unsatisfiable on the decommission path - wiping violates rule 2, retiring
unwiped violates rule 3. (This finding is why the skill now requires a
joint-satisfiability check on transcribed rules before they ship.)

Outcome: findings only, nothing changed. The agent ran the real committed
monitor over three flows and reported the deciding events for each:
quarantine->wipe->retire violates rule 2 at the wipe; quarantine->retire
violates rule 3; a never-decommissioned device pends forever. It laid out
four options - broaden rule 2's allowed set to blocked-or-wiped
(recommended, verified end-to-end to keep every attacker case caught),
close rule 2's window at the wipe with `until` (weaker), hide wipe/retire
from the monitor (explicitly advised against as instrumentation reshaping
to dodge the monitor), or accept the noise - and waited.

## Turn 5 - the sanctioned repair

> That's the straight answer I wanted, and you're right - I wrote rule 2
> wider than I meant it. Option A: after quarantine, everything must be a
> blocked rejection or the decommission wipe. Reword my rule 2 that way -
> the 'contained' step is fine. Regenerate what needs regenerating as one
> intended change, add the clean decommission flow to the demo so I can
> see quarantine -> wipe -> retire go green, rerun all gates, re-pin as
> needed, and report.

Outcome: a listener-side-only repair - the `wiped` event already existed,
so no application code changed; one new predicate step ("a device is
contained": blocked or wiped) and the user's rule 2 reworded to
`Then a device is contained since a device is "quarantined"`. Intended
contract change per protocol (pre-save diff: one step added, all ten emit
sites unchanged), catalog regenerated, replay 33 verdicts and 5
violations. Verified behaviour: the decommission path goes green on all
three device rules, while an attacker's post-quarantine action, a
post-wipe action, and an unwiped retirement all still violate. That final
state is what this directory holds.
