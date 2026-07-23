# How the rv skill works

This guide explains the skill end to end: what an agent skill is and how a
coding agent picks this one up, what the agent is instructed to do at every
stage of development, and how each part of
[behave-rv](https://github.com/moraneus/behave-rv) is used along the way. It
is the connective narrative; the per-topic depth lives in the
[references](../skills/rv/references/) and in behave-rv's own shipped
documentation (`python -m behave_rv docs`).

## 1. The idea in one paragraph

Runtime verification is usually retrofitted: the system is built, then
someone bolts monitoring on. This skill inverts that. Loaded into a coding
agent, it changes how the agent develops so the software is *born
monitorable*: every state transition emits an event as the code is written,
the user's behavioural requirements become deterministic Gherkin policies,
and a machine-checked stability contract stops policies from rotting when
the agent rewrites code. The product that leaves development carries a
runtime monitor inside it.

## 2. What an agent skill is, mechanically

A skill is a directory of instructions the agent loads on demand:

```
skills/rv/
  SKILL.md            the entry point: role, guardrails, workflow
  references/         seven focused documents, read when needed
  templates/          the monitoring/ scaffold copied into projects
```

`SKILL.md` starts with frontmatter — a `name` and a `description`. The
description is the trigger: the agent reads it alongside its other skills
and activates this one when the situation matches. This skill's description
fires in four situations:

1. Building or modifying an application that should ship with monitoring.
2. The user states behavioural requirements — lifecycles, deadlines,
   prohibitions, SLAs — in any prompt.
3. Application code changes in a project that already has a `monitoring/`
   directory.
4. The user explicitly invokes `/rv`.

The body of `SKILL.md` is deliberately short. It carries the guardrails and
the workflow, and delegates everything detailed to the references so the
agent loads only what the current step needs (this is called progressive
disclosure — a skill that front-loads everything crowds out the actual
task). The references are:

| Reference | The agent reads it when |
|---|---|
| `cheatsheet.md` | writing any behave-rv code — API in one page |
| `operators.md` | drafting or checking a policy — all nine temporal forms and the compiler's refusals |
| `instrumentation.md` | writing or editing application code — the emission conventions |
| `policy-authoring.md` | turning a requirement sentence into a scenario |
| `stability.md` | running or interpreting the catalog gates |
| `project-files.md` | creating or maintaining the `monitoring/` layout |
| `questionnaire.md` | the user invokes `/rv` |

For anything deeper than the references, the agent reads behave-rv's
complete documentation offline from the installed package —
`python -m behave_rv docs <name>` — which always matches the installed
version.

Installation is either the Claude Code plugin route
(`/plugin marketplace add moraneus/rv-monitoring-skill`, then
`/plugin install rv-monitoring@rv-monitoring-skill`) or `./install.sh`,
which copies `skills/rv/` into `~/.claude/skills/`. Both deliver the
identical directory.

## 3. The three roles (the trust model)

Everything the skill instructs follows from one separation:

1. **The agent** writes the application, the instrumentation, and the step
   predicates. It *proposes* policies; it never owns them.
2. **The user** owns the policies. Only the user decides what goes into
   `monitoring/policies/`.
3. **The deterministic engine** owns the verdicts. No model, heuristic, or
   randomness ever enters the runtime path.

This is what makes the monitoring trustworthy rather than an LLM grading
its own work: the specification is human-owned, the verdict is computed by
a deterministic engine, and the agent's job is to keep the bridge between
them intact. The skill's hard guardrails are this separation stated as
rules: never commit a policy, never edit a user's policy, never hand-edit
the catalog, never silently regenerate it to make a break disappear, never
put anything dynamic in the runtime path.

## 4. What the agent maintains in a project

The skill has the agent create and keep current one directory:

```
monitoring/
  steps.py                 the vocabulary: build_registry() + load_policies()
  policies/                USER-OWNED .feature files (one Feature per file)
  catalog.json             the generated two-sided contract, committed
  STEPS.md                 GENERATED authoring doc for the user
  SUGGESTED_POLICIES.md    the agent's proposals, with rationale
  generate_steps_doc.py    renders STEPS.md from the live registry
  replay_check.py          scripted traffic + exit-coded verdict gate
  traces/                  recorded event streams
```

Projects that lack this layout are bootstrapped from
`skills/rv/templates/monitoring/`, which ships working versions of every
file with `__PROJECT__` / `__ENTITY__` / `__DOMAIN__` / `__KEY__`
placeholders the agent instantiates for the domain at hand.

Two of these files exist purely for the *user*: `STEPS.md` documents every
registered phrasing, its parameters, the event it observes, and
ready-to-copy example scenarios — so the user can author policies without
reading Python — and `SUGGESTED_POLICIES.md` is where every agent proposal
lands with a rationale, waiting for the user's accept or reject.

## 5. The development loop

The skill prescribes the same six steps for *every* change — a new feature,
a refactor, or a new prompt against existing code:

1. **Extract requirements.** If the prompt contains behavioural language
   ("orders must be refunded within 5 seconds", "never ship after cancel"),
   the agent classifies each sentence against the extraction table in
   `policy-authoring.md` and maps it to one of the nine temporal forms.
   Requirements the fragment cannot express — cross-entity relations,
   counting, aggregates — are declared out of fragment honestly, with the
   nearest in-fragment restatement offered as a labelled alternative. The
   skill forbids silent approximation.
2. **Write the code, instrumented.** Every state transition, lifecycle
   boundary, and external interaction emits an `Event(...)` at the site,
   following the conventions in `instrumentation.md` (section 7.1 below
   explains why each convention exists). The rule is additive-only:
   emissions sit beside the business logic and never reshape it.
3. **Expose steps.** The agent registers or extends predicates in
   `monitoring/steps.py` — stable `step_id`s, pure predicates, aliases
   whenever a phrasing is reworded — then regenerates `STEPS.md` so the
   user's authoring surface stays complete.
4. **Propose.** New monitorable behaviour with no covering policy becomes a
   suggestion in `SUGGESTED_POLICIES.md`: the draft scenario, the rationale,
   and the events it observes. Every suggestion is compiled against the
   current registry before it is proposed — a suggestion that would not
   compile is noise.
5. **Gate.** Two commands, every non-zero exit either fixed or reported:

   ```bash
   python -m behave_rv catalog diff \
     --steps monitoring/steps.py --catalog monitoring/catalog.json \
     --policies monitoring/policies --app <application .py files> \
     --fail-on-app-risk [--trace monitoring/traces/<representative>.jsonl]
   python monitoring/replay_check.py
   ```

   The first is the static stability contract (section 7.6); the second is
   the dynamic one (section 7.7). `catalog save` — regenerating the
   contract — is permitted only for an *intended* contract change, in the
   same commit, stated in the report.
6. **Report.** What was instrumented, what the gates said, what was
   suggested, what is at risk.

## 6. `/rv` — the interactive consultation

When the user types `/rv`, the agent runs a structured interview
(`questionnaire.md`) instead of guessing what to monitor: entities and
their correlation keys first, then lifecycles and terminal events, then
prohibitions, then deadlines and SLAs with concrete numbers, then
eventualities and invariants, then priorities and out-of-fragment wishes.
Questions the codebase already answers are read from it and confirmed, not
asked. The output is a written plan — event vocabulary, step phrasings,
draft policies grouped by interview section, instrumentation points, and
gate wiring — presented for approval before any code changes. On approval
the plan executes through the development loop above.

## 7. How each part of behave-rv is used

### 7.1 The `Event` — the observable unit

Everything the monitor sees is one frozen record:

```python
Event(
    type="order.status",          # stable identity, dotted lowercase
    event_time=clock(),           # float seconds, EVENT time, never receipt time
    bindings={"order_id": oid},   # which entity this is about
    payload={"status": "paid"},   # the observable fields
    source="order-service",       # provenance
)
```

The skill's instrumentation conventions all exist to keep these emissions
*analyzable* and *correct*:

- `Event(...)` is constructed literally at the emission site because that
  construction is the anchor behave-rv's static analysis keys on; hiding it
  behind a factory blinds the stability contract.
- Event types are module-level string constants — the analyzer resolves
  constants, while an f-string degrades to a declared `<dynamic>` marker.
- `emit` and `clock` are injected through the constructor, so the same
  service runs live (real clock, events to the engine) and under the replay
  gate (fake clock, scripted traffic) with identical code.
- Ordered actions carry distinct timestamps, because the engine orders
  equal timestamps canonically by content, not by arrival.
- Live services use a service-relative clock (`time.time() - start`) so
  wall-clock deadlines behave.

### 7.2 The `StepRegistry` — the vocabulary policies bind to

`monitoring/steps.py` defines a side-effect-free `build_registry()` factory
(the behave-rv CLI detects it by name). Each step is a *pure predicate*
with a Gherkin phrasing and a permanent identity:

```python
@registry.trigger('an order is "{status}"', step_id="order.status.is",
                  event_type="order.status", correlation_key="order_id")
def order_is(ctx, event, status):
    return (event.type == "order.status"
            and event.payload.get("status") == status)
```

Three properties carry the whole design:

- **Purity.** The predicate reads the event and returns a boolean —
  nothing else. This keeps the runtime path deterministic.
- **Permanent identity.** Policies and the catalog bind to `step_id`, so
  renaming the function or reformatting the code costs nothing. A
  `step_id` is never reused for a different meaning.
- **Aliases on rewording.** `registry.alias("order.status.is", 'the order
  reaches "{status}"')` keeps old policy text compiling when a phrasing
  improves. The skill requires the alias in the same change as the
  rewording; the catalog then reports the change as `renamed`, not a break.

The correlation key declared on the step is how the engine shards: one
monitor instance per distinct key value, so "order 4471" and "order 4472"
are verified independently.

### 7.3 The compiler — from a user's sentence to a monitor

`compile_feature(text, registry)` turns each `Scenario` into one `Policy`:
the scenario name becomes the policy id, the step texts resolve against the
registered phrasings and aliases, and the temporal suffix selects one of
nine forms — `never happens`, `has happened`, `always holds`, `since`,
`before`, `previously`, `within "<n>" seconds`, and plain or
`until`-bounded `Given` scopes on `never` (full semantics: `operators.md`
or `python -m behave_rv docs operators`). For example:

```gherkin
Scenario: a cancelled order is refunded in time
  When an order is "cancelled"
  Then an order is "refunded" within "5" seconds
```

The compiler *refuses* anything outside the fragment — multiple `Then`
steps, cross-entity scenarios, unrecognized suffixes — with a message that
states exactly what is wrong. The skill treats every refusal as a precise
repair instruction and every accepted policy as therefore trustworthy:
because the compiler never approximates, whatever it accepts has a defined
verdict on any finite stream.

### 7.4 The engine — deterministic verdicts per entity

```python
engine = Engine(policies, terminal_event_types={"order.done"})
verdicts = engine.run(source, emit_pending=True)
```

The engine consumes events from any source — the in-process queue in a
live service, a scripted `InProcessSource` in the replay gate, a
`ReplaySource` over a recorded file — and produces three-valued verdicts
(`satisfied` / `violated` / `pending`) per policy per entity. The facts
the skill makes the agent respect:

- Verdicts are decided on **event time**, never receipt time.
- `within` deadlines are violated by a *timer*, not an arriving event —
  absence is the violation.
- **Terminal events** (`order.done`) settle an entity: prohibitions become
  satisfied, unfulfilled obligations become violated, and the entity's
  monitor state is reclaimed. The agent declares one per entity type whose
  lifecycle genuinely ends, and warns the user when proposing
  `has happened` policies for entities that have none (they can pend
  forever).
- `emit_pending=True` reports honest pending verdicts at the end of a
  replay instead of hiding them.

### 7.5 Verdicts and explanations — the counterexample is the policy

Each `Verdict` carries the policy id, the entity key, the trigger event,
and the witnessing trace. `explain_verdict` renders a violation as the
*user's own scenario*, replayed: the authored Gherkin with the failing step
marked and the real events and values that drove the entity there. The
replay gate prints this for every violation, so a red gate reads as a
counterexample in the same words the requirement was written in.

### 7.6 The catalog — the two-sided stability contract

This is why the skill can let an agent rewrite code aggressively.
`monitoring/catalog.json`, generated by `catalog save` and committed, is a
fingerprint of *both* sides of the monitoring bridge:

- **The listener side:** every step's contract — phrasing, parameters,
  event type, correlation key, predicate fingerprint — keyed by `step_id`.
- **The shouter side:** every `Event(...)` emission site in the
  application, with its emitted interface (event type, binding keys,
  payload keys) and a fingerprint of its *dependency slice* — the emitting
  function, its transitive callers and callees, the constants and
  decorators they touch.

`catalog diff --app --fail-on-app-risk` compares the current code against
the committed contract and classifies every change:

- `renamed` — a pure representational change (function renamed, code
  reformatted, class renamed). **Absorbed silently.** This is what lets
  refactoring stay free.
- `changed` / `removed` (step side) and `interface-break` / `removed`
  (app side) — the contract itself moved. **A break**, scoped to exactly
  the policies whose steps or observed event types are affected.
- `behavior-risk` (app side) — the emitted interface is intact but code in
  the emission's dependency slice changed, named down to the function. The
  policy may now see different behaviour even though nothing about the
  event's shape moved.
- `added` — new monitorable surface; suggestion material for step 4 of the
  loop.

The skill's break protocol is strict: an unintended break or risk stops
the work, the diff output is shown to the user verbatim, and the agent
proposes either restoring the contract in code or — only with the user's
approval — regenerating the catalog. The one absolute prohibition is
silence: the catalog is never hand-edited, never regenerated to make a
break disappear, and a policy is never deleted to make the diff pass.

### 7.7 The replay gate — the dynamic check behind the static one

The static diff says a change *may* affect a policy; `replay_check.py`
says whether it *did*. It drives every seeded flow — healthy and faulty —
through the real service with a fake clock (`tick()` between ordered
actions), runs the real policies over the resulting stream, prints every
verdict and every explanation, and exits non-zero unless the counts match
the pinned `EXPECTED` values. The pins are an oracle: the agent updates
them only for intended behaviour changes, and says so.

### 7.8 Traces and liveness — the net under everything

`TraceRecorder` tees a live stream into `monitoring/traces/*.jsonl`;
`ReplaySource` runs the identical pipeline over a recorded file. The skill
uses traces twice: a new policy can be tested against last week's traffic
before it is deployed, and `catalog diff --trace` raises a *liveness
warning* for any policy whose event types or bound values never appear in
a representative stream — the catch-all for the one gap static analysis
cannot see, a value renamed on the application side (the code still emits
`order.status`, but the status is now `"complete"` while the policy says
`"completed"`).

### 7.9 The dashboard and CI

`Dashboard(policies, registry=..., catalog=..., app=...)` serves live
verdicts and — because it is constructed with the registry, the committed
catalog, and the application files — shows the same two-sided contract
state at runtime that the diff checks at build time. In CI, the shipped
`ci-snippet.yml` template runs the diff with `--fail-on-app-risk` plus the
replay gate on every push, so the contract gates the merge, not just the
conversation.

## 8. A worked pass through the loop

This is the exact flow the skill repository's own CI validates end to end
(`test/e2e.sh`) against the published behave-rv package. The user asks for
a ticket system where *a ticket may only complete after it was started*.

**Instrumented code** (loop step 2 — constants, literal `Event(...)`
anchors, injected `emit`/`clock`, a terminal event, distinct timestamps):

```python
EVENT_TYPE = "ticket.status"
TERMINAL_TYPE = "ticket.done"

class TicketService:
    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock

    def _status(self, ticket_id, status):
        self._emit(Event(EVENT_TYPE, self._clock(), {"ticket_id": ticket_id},
                         {"status": status}, "ticketing"))

    def start(self, ticket_id):
        self._status(ticket_id, "started")

    def complete(self, ticket_id):
        self._status(ticket_id, "completed")
        self._emit(Event(TERMINAL_TYPE, self._clock() + 1e-3,
                         {"ticket_id": ticket_id}, {}, "ticketing"))
```

**One step** in `monitoring/steps.py` (loop step 3): the phrasing
`a ticket is "{status}"`, `step_id` `ticket.status.is`, observing
`ticket.status` with key `ticket_id`. `STEPS.md` regenerated.

**The policy the user owns** — the requirement is "X only after Y", so the
extraction table gives `before`:

```gherkin
Scenario: a ticket may only complete after it was started
  When a ticket is "completed"
  Then a ticket is "started" before
```

**The gates** (loop step 5): `catalog save` records one step and two
emission sites; `catalog diff` comes back clean; the replay gate runs a
healthy ticket (started, then completed — `satisfied`) and a faulty one
(completed without start — `violated`, explained as the scenario with the
`Then` step marked).

**Then the agent refactors.** Suppose a later change adds a guard:

```python
def start(self, ticket_id):
    if ticket_id:
        self._status(ticket_id, "started")
```

The emitted interface is untouched — same event type, same keys — so no
test of the event's *shape* would notice. But `start` is in the dependency
slice of a `ticket.status` emission, so `catalog diff --app` reports
`behavior-risk` naming `TicketService.start`, scoped to the policy above,
and exits non-zero. The skill's protocol takes over: stop, show the user
the diff verbatim, and wait for direction. That is the central promise —
a change that could silently starve a policy becomes a named, gating
event instead.

## 9. Division of labour, summarized

| | Agent | User | Engine |
|---|---|---|---|
| Application code + instrumentation | writes | reviews | — |
| Step vocabulary (`steps.py`, `STEPS.md`) | writes + regenerates | authors policies from it | — |
| Policies (`policies/*.feature`) | proposes only | **owns** | compiles + monitors |
| Catalog (`catalog.json`) | regenerates on intended changes only | approves contract changes | — |
| Gates (diff + replay) | runs on every change | sees breaks verbatim | computes the results |
| Verdicts at runtime | — | reads explanations | **owns** |

## 10. How the skill itself is kept honest

The repository's CI installs the *latest published* behave-rv from PyPI on
every push and weekly, scaffolds a project from the templates, and runs the
whole story above: policy compiles, verdicts are correct, `STEPS.md`
generates, the catalog saves and diffs clean, the injected guard is flagged
as `behavior-risk` with the right function named, and the shipped
documentation resolves offline. A behave-rv release that breaks any of the
skill's mechanics turns the badge red before a user ever hits it.
