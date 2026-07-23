---
name: rv
description: Develop software with embedded behave-rv runtime verification. Use when building or modifying an application that should ship with runtime monitoring, when the user states behavioural requirements (lifecycles, deadlines, prohibitions, SLAs), when application code changes in a project that has a monitoring/ directory, or when the user invokes /rv for an interactive monitoring consultation. Turns requirements into Gherkin policies, instruments code with events while writing it, keeps the two-sided stability contract green on every change, and maintains the user's policy-authoring vocabulary.
---

# rv: develop software that is born monitorable

You are developing with [behave-rv](https://github.com/moraneus/behave-rv):
a runtime-verification framework where policies are controlled Gherkin
scenarios compiled into deterministic per-entity monitors over the
application's event stream. Your job is to make the software monitorable *as
you write it* - not as an afterthought - while keeping three roles strictly
separate:

1. **You (the agent)** write the application, the instrumentation, and the
   step predicates. You *propose* policies; you never own them.
2. **The user** owns the policies. Only the user moves a policy into
   `monitoring/policies/`.
3. **The deterministic engine** owns the verdicts. No model, heuristic, or
   randomness ever enters the runtime path.

This separation is what makes the monitoring trustworthy. Everything below
serves it.

## Hard guardrails (non-negotiable)

- **Propose policies; never commit them.** Draft policies go to
  `monitoring/SUGGESTED_POLICIES.md` with a rationale each. The user decides
  what becomes a policy. One exception, transcription: a rule the user
  states imperatively in their request ("orders must never ship after
  cancel") is user-authored. Transcribe it faithfully into
  `monitoring/policies/` and say so in your report. Everything YOU thought
  of goes through `SUGGESTED_POLICIES.md`.
- **Never edit a policy the user wrote** - not its text, not its meaning -
  without the user explicitly asking. Never weaken a policy to make code
  pass; if code violates a policy, the code is wrong until the user says
  otherwise.
- **Never hand-edit `monitoring/catalog.json`.** It is generated
  (`catalog save`) and committed. Regenerate it only for an intended
  contract change, in the same commit as that change, and say so.
- **Every `catalog diff` break is a stop-and-report event.** Show the user
  the tool's output verbatim, explain what moved, and wait for direction.
  Never silently regenerate the catalog to make a break disappear.
- **Nothing dynamic in the runtime path.** Step predicates are pure
  (read the event, return a boolean); the engine stays model-free.

## The project layout you create and maintain

```
monitoring/
  steps.py                 # the vocabulary: build_registry() + load_policies()
  policies/                # user-owned .feature files (one Feature per file)
  catalog.json             # generated two-sided contract, committed
  STEPS.md                 # GENERATED vocabulary doc for the user (never hand-edit)
  SUGGESTED_POLICIES.md    # your proposals, with rationale
  generate_steps_doc.py    # renders STEPS.md from the registry
  replay_check.py          # scripted traffic + exit-coded verdict gate
  traces/                  # recorded streams for liveness checks
```

Bootstrap a project that lacks this layout from the templates shipped
next to this file (`templates/monitoring/`), then run
`pip install behave-rv` (>= 0.2.0, Python 3.10+). Full layout rules:
[references/project-files.md](references/project-files.md).

## The development loop

Run this loop for EVERY change - a new feature, a refactor, or a new user
request against existing code:

1. **Extract requirements.** If the user's prompt contains behavioural
   requirements ("orders must be refunded within 5 seconds", "never ship
   after cancel", "every ticket eventually resolves"), map each one to the
   temporal fragment using
   [references/policy-authoring.md](references/policy-authoring.md).
   Requirements outside the fragment (cross-entity, aggregates, unbounded
   liveness needing a violated verdict) - tell the user honestly that they
   are out of fragment and why; never approximate silently.
2. **Write the code, instrumented.** Every state transition, lifecycle
   boundary, and external interaction emits an `Event(...)` following the
   conventions in
   [references/instrumentation.md](references/instrumentation.md) - those
   conventions are what the stability analysis anchors on. Over-expose:
   an unused event is cheap; a missing one is a policy nobody can write.
3. **Expose steps.** Register or extend predicates in `monitoring/steps.py`
   (stable `step_id`s, pure predicates, aliases on rephrasing). Then
   regenerate the user's vocabulary: `python monitoring/generate_steps_doc.py`.
4. **Propose.** New monitorable behaviour with no covering policy → add a
   suggestion to `monitoring/SUGGESTED_POLICIES.md`: the draft scenario, the
   rationale, and which events it observes.
5. **Gate.** Run, in order, and treat every non-zero exit as a defect to fix
   or a break to report (details:
   [references/stability.md](references/stability.md)):

   ```bash
   python -m behave_rv catalog diff \
     --steps monitoring/steps.py --catalog monitoring/catalog.json \
     --policies monitoring/policies --app <application .py files> \
     --fail-on-app-risk [--trace monitoring/traces/<representative>.jsonl]
   python monitoring/replay_check.py
   ```

   A policy that fails to compile is a repair signal, not an obstacle - the
   compiler's refusals state exactly what is wrong. On intended contract
   changes only: `catalog save --steps ... --catalog ... --app ...`,
   committed with the change, explained to the user. A flagged change is
   INTENDED only when the observable behaviour it names is itself what the
   user asked for - not a side effect of how you implemented something
   else. When in doubt, treat it as unintended: stop and report. Either
   way, quote the pre-save diff output verbatim in your report.
6. **Report.** Use this skeleton every time - fill every line ("none" is a
   valid value); the diff/replay lines quote the tools, not your summary of
   them:

   ```markdown
   ## Monitoring report - <the change>
   - Instrumented: <events added/changed, and where>
   - Vocabulary:   <steps added/aliased; STEPS.md regenerated>
   - Gates:        catalog diff <clean | N break(s)/risk(s), shown verbatim above>;
                   replay <N verdicts, N violation(s) vs pinned>
   - Suggested:    <new SUGGESTED_POLICIES.md entries, by title>
   - Live view:    <dashboard URL | how to start it>
   - At risk / out of fragment: <items>
   ```

## The live view - expose it, and tell the user

behave-rv ships a built-in web dashboard (`behave_rv.dashboard.Dashboard`,
stdlib-only). Whenever you wire the application to run live - an entry
point, a demo, a service startup - expose it. This is not optional: the
user follows their policies and the event log there, in their own words,
while the app runs.

```python
dashboard = Dashboard(policies, registry=registry,
                      catalog="monitoring/catalog.json",
                      app=["app/service.py"])      # both contract sides on-page
url = dashboard.start(port=7007)
print("live monitor:", url)                        # the app announces it too
# feed it events where you emit: source.push(dashboard.tap(event))
engine.run(source, sink=dashboard.sink)
```

Then ALWAYS tell the user, in the report's "Live view" line and in prose
the first time: the URL (default `http://127.0.0.1:7007`) and what they
will see there - every policy as a card with its per-entity verdicts, the
rendered explanation for each violation, the live event feed, and the
stability strip showing whether the code still matches the committed
contract. If the project currently runs only under the replay gate, say
that the dashboard exists and will be wired the moment there is a live
entry point.

## /rv - the interactive consultation

When invoked as `/rv`, run the structured interview in
[references/questionnaire.md](references/questionnaire.md): entities and
correlation keys first, then lifecycles, prohibitions, deadlines and SLAs,
eventualities and terminal events. Use the AskUserQuestion tool when
available. The output is a written plan: proposed event vocabulary, step
phrasings, draft policies (as suggestions), and the instrumentation points -
then, on the user's go, execute it via the loop above.

## Knowing behave-rv

The condensed, self-contained references shipped with this skill:

- [references/cheatsheet.md](references/cheatsheet.md) - Event model, step
  decorators, engine options, live wiring, dashboard, CLI, in one page.
- [references/operators.md](references/operators.md) - all nine temporal
  forms with semantics, examples, and the compile-time refusals.
- [references/instrumentation.md](references/instrumentation.md) - the
  emission conventions and why the analyzer needs each one.
- [references/policy-authoring.md](references/policy-authoring.md) - from a
  requirement sentence to a compiling scenario.
- [references/stability.md](references/stability.md) - the two-sided
  catalog, reading diff output, the break protocol, CI wiring.
- [references/project-files.md](references/project-files.md) - the
  monitoring/ layout and file conventions.
- [references/questionnaire.md](references/questionnaire.md) - the /rv
  interview and the answer-to-operator mapping.

For anything deeper, the COMPLETE documentation ships inside the installed
package and always matches its version - read it offline:

```bash
python -m behave_rv docs              # list: guide, operators, semantics,
python -m behave_rv docs guide        #   stability, experiments, mutation,
python -m behave_rv docs stability    #   app-surface-evaluation
```

Prefer these over web fetches. The same documents are also on GitHub:
[behave-rv/docs](https://github.com/moraneus/behave-rv/tree/main/docs).
