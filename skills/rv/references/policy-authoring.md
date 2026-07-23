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
`within` plus offline analysis of verdicts).

## File and naming conventions

- One `Feature` per `.feature` file, in `monitoring/policies/`, numbered for
  stable ordering: `01_paid_after_auth.feature`.
- The **scenario name is the policy id** - unique across the project, and it
  is what verdicts, dashboards, and break reports display. Write it as the
  requirement in plain words: `an order may only be paid after it was
  authorized`.
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
