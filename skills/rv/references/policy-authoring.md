# From a requirement sentence to a compiling policy

## The extraction table

When a user prompt contains a behavioural requirement, classify it:

| The user says something like | Fragment form | Draft shape |
|---|---|---|
| "X must happen before Y" / "only after" | `before` | `When <Y>` / `Then <X> before` |
| "immediately after" / "the step right before" | `previously` | `When <Y>` / `Then <X> previously` |
| "within N seconds/minutes" / SLA / deadline | `within` | `When <trigger>` / `Then <response> within "<n>" seconds` |
| "never" / "must not" / "forbidden" | `never` | `Then <X> never happens` |
| "while/once CONDITION, never" | scoped `never` | `Given <cond> [until <close>]` / `Then <X> never happens` |
| "eventually" / "must at some point" | `has happened` | `Then <X> has happened` (warn: needs a terminal event to ever violate) |
| "always" / "every event is" | `always holds` | `Then <X> always holds` |
| "from the moment Q, P stays true" | `since` | `Then <P> since <Q>` |

Out of fragment - say so, do not approximate silently: relations between two
independent entities ("every order belongs to an active user"), counting and
aggregates ("no more than 3 retries", "95% of requests"), unbounded liveness
that must produce a violation on a finite prefix. Offer the nearest
in-fragment property as a labelled alternative (retries → often re-expressible
as a scoped `never` on a distinct event; percentile SLAs → per-entity
`within` plus offline analysis of verdicts), and build it only after the
user accepts it - unless the user's request itself already specifies the
approximated behaviour (an explicit "alert me per wave" is an acceptance
of occurrence keying), in which case ship it with the fragment split
stated plainly in the report.

**Joint satisfiability.** Before shipping transcribed rules, walk every
normal flow the user DESCRIBED through all the rules together, and check
each path stays legal. Rules that are individually sensible can jointly
forbid a lifecycle the user relies on - "after quarantine nothing but
rejections may happen" plus "every retired device was wiped first" leaves
a quarantined device no legal way out: wiping violates the first rule,
retiring unwiped violates the second. Verify empirically (run the compiled
policies over the described flows), and surface any conflict with concrete
options BEFORE the policies ship - the user chooses the resolution; a
conflict discovered by a production violation is a failure of this step.
The replay gate enforces this mechanically: every described healthy flow
belongs in ``replay_check.py``'s scripted traffic with zero violations
expected, so a jointly-unsatisfiable rule set turns the gate red at build
time instead of paging someone in production. THE WAITING POSTURE: while
a conflict awaits the user, the user's LITERAL transcription stays in
``policies/`` - with the gate red if that is the cost - and your candidate
readings stay in ``SUGGESTED_POLICIES.md`` as options. The policy files
hold the user's words, never your interpretation of them.

**Blind spots are contract.** A policy only sees the event types its
steps observe; everything else bypasses it. Whenever plain language
suggests total coverage ("nothing else may happen", "only ever", "at
every step") - the `since`, `always holds`, and scoped `never` forms -
state in your report which event types the policy observes and which
bypass it ("retirement is a separate event type and is invisible to this
rule"), so the user learns the boundary from you, not from an incident.
The same applies to ENUMERATED VALUES: a predicate that lists forbidden
statuses ("captured" or "authorized") is silently bypassed by any status
added later - say so, and prefer phrasing the predicate over an intent
("new charge activity") so a future status lands inside the rule by being
classified, not outside it by being unlisted.

**Terminal windows.** A terminal event does not just free memory - it
SETTLES every open policy on the entity, prohibitions included, and a
scoped `never` settles as `satisfied`. So a prohibition on an entity whose
lifecycle emits a terminal is only armed from its scope opening until the
terminal: a forbidden event arriving after the close is invisible, and the
dashboard showed green first - a false-green, worse than a miss. The rule:
for every scoped prohibition (`Given ... never`, `since`) on an entity
with a terminal, the FAULT seeds in `replay_check.py` must include an
occurrence arriving AFTER the entity's real closing behaviour, through the
real service path. If that seed is not caught, the policy's guarantee is
really `min(time-to-terminal, quiescence TTL)` - surface that window to
the user as a decision (keep the terminal and accept the window, drop the
terminal and guard with a TTL, or re-key the rule to a longer-lived
entity). Never let a demo "prove" a prohibition with seeds that dodge the
terminal the real path emits.

**Key projection.** Before declaring a rule cross-entity, check whether it
becomes per-entity under a DIFFERENT correlation key. "A fined member's
loans are never renewed" relates loans to members - but emitting a
member-keyed event at the renewal site (`member.renewal`) turns it into one
rule about members: `Given a member's fine is "owed" until a member's fine
is "paid_off"` / `Then a member renews a loan never happens`. Adding an
emission under the right key is additive instrumentation, not reshaping.
Flag the added event in your report as part of the proposal, so the user
can reject the extra surface along with the policy.

**Occurrence keying.** A `never happens` prohibition settles at its first
violation, so a singleton entity alerts once, ever. When the user wants an
alert PER occurrence (each attack wave, each breach episode), key the
event by the occurrence instead of the singleton: the app stamps each
episode with a fresh id (`wave_id`) and emits under that key, every
episode becomes a new entity whose policy violates exactly once, and the
quiescence TTL reclaims old episodes. Alert-per-wave, still fully
in-fragment.

## File and naming conventions

- One `Feature` per `.feature` file, in `monitoring/policies/`, numbered for
  stable ordering: `01_paid_after_auth.feature`.
- The **scenario name is the policy id** - unique across the project, and it
  is what verdicts, dashboards, and break reports display. Write it as the
  requirement in plain words: `an order may only be paid after it was
  authorized`. Because the name is the id, renaming a scenario ORPHANS its
  verdict history: dashboards and recorded verdicts show the old and new
  names as unrelated policies. When a user-requested reword changes a
  scenario name, state that continuity cost in your report so the break in
  the timeline is a known decision, not a surprise.
- One correlation key per scenario (composite tuple allowed). The key comes
  from the steps used; the `.feature` never mentions it.
- Steps resolve by text against registered phrasings and their aliases. If
  you reword a phrasing in `steps.py`, KEEP the old wording as an alias or
  every policy using it stops compiling - and that refusal is itself
  reported as a stability failure.

## Worked example

Requirement: *"a cancelled order must be refunded within 5 seconds, and a
cancelled order must never ship."*

```gherkin
Feature: cancellation safety

  Scenario: a cancelled order is refunded in time
    When an order is "cancelled"
    Then an order is "refunded" within "5" seconds

  Scenario: a cancelled order is never shipped
    Given an order is "cancelled"
    Then an order is "shipped" never happens
```

Requires: a `trigger` step phrased `an order is "{status}"` observing
`order.status` with key `order_id`, and the application emitting
`cancelled` / `refunded` / `shipped` status events. Check both ends exist
before proposing; if the events are missing, instrument first.

## The suggestion protocol

You propose; the user disposes. Append to
`monitoring/SUGGESTED_POLICIES.md`:

```markdown
## <date>: <short title>

**Observes:** <event types / steps>
**Why:** <one or two sentences: the risk this catches>

​```gherkin
Feature: ...
  Scenario: <plain-words policy id>
    ...
​```
```

Verify every suggestion compiles against the current registry before
proposing it (`compile_feature` on the draft - a refused suggestion is
noise). When the user accepts one, move it into `monitoring/policies/`
yourself only when they say so, then rerun the gates.
