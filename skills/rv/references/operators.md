# The temporal vocabulary: all nine forms

Every policy is one `Scenario` = one monitor per entity, three-valued
verdicts (`satisfied` / `violated` / `pending`). Every form below has a
defined verdict on a finite stream - that is the fragment's design rule.

## Self-contained forms (a `Then` alone; no `When`)

| Form | Meaning per entity | Violates | Satisfies |
|---|---|---|---|
| `Then <p> never happens` | the named event must never occur | at the first `<p>` event | at the terminal event |
| `Then <p> has happened` | must occur at some point | at terminal if it never occurred | at the first `<p>` event |
| `Then <p> always holds` | every event for the entity is a `<p>` event | at the first non-`<p>` event | at terminal |
| `Then <p> since <q>` | after `<q>`, `<p>` holds at every later event | first event where `<p>` fails after `<q>` (no re-anchor) | at terminal (incl. vacuously if `<q>` never occurred) |

## Triggered forms (`When` + `Then`)

| Form | Meaning | Notes |
|---|---|---|
| `When <q>` / `Then <p> before` | the trigger must be preceded by `<p>` | decided at the trigger; a single event matching both satisfies |
| `When <q>` / `Then <p> previously` | the event immediately before the trigger is `<p>` | trigger as the entity's first event violates |
| `When <q>` / `Then <p> within "<n>" seconds` | after the trigger, `<p>` before the deadline | violated by the timer when the deadline passes; a response exactly AT the deadline is too late |

## Scoped prohibition (`Given` + `Then never`)

```gherkin
Given an order is "cancelled"                     # latching: once open, open forever
Then an order is "shipped" never happens

Given a user is "locked" until a user is "unlocked"   # interval: closes, may reopen
Then a user is "action" never happens
```

The scope state updates before the forbidden check: an event that opens the
scope and matches the prohibition violates; an event that closes it and
matches is permitted.

## Examples, one per form

```gherkin
Then an order is "double_charged" never happens
Then an invoice is "issued" has happened
Then a sync is "ok" always holds
Then an order is "reviewed" since an order is "flagged"

When an order is "paid"
Then an order is "authorized" before

When a user is "locked"
Then a user is "login_fail" previously

When an order is "cancelled"
Then an order is "refunded" within "5" seconds

Given an order is "cancelled"
Then an order is "shipped" never happens
```

## What the compiler REFUSES (never approximates)

- More than one `Then`; `And`/`But` multi-step scenarios.
- A `When` on the self-contained forms; a missing `When` on triggered forms.
- `Given` on any operator other than `never`.
- Any unrecognized temporal suffix.
- **Cross-entity policies**: a scenario whose steps reference more than one
  correlation key. The fragment is one key per scenario (a composite tuple
  key is allowed for one joint identity).
- Non-finite `within` durations.

Treat every refusal as a precise repair instruction. Requirements that need
what the fragment refuses (relations between independent entities, counting,
aggregates, unbounded liveness that must produce a `violated` verdict on a
finite prefix) are OUT OF FRAGMENT: say so to the user explicitly, and offer
the nearest in-fragment property (e.g. bounded response via `within`, or a
per-entity restatement) as a clearly-labelled approximation for them to
accept or reject.

## Fragment notes agents get wrong

- `has happened` stays honestly `pending` until the event or a terminal -
  configure a terminal event type or it may pend forever on a live stream
  (the engine warns).
- `before` is any-past-event precedence; `previously` is the immediate
  predecessor. Do not use `previously` for "at some point earlier".
- One trigger, one obligation per scenario. Compound requirements become
  several scenarios.
