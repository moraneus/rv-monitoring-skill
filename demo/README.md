# Demo: a project built end-to-end by an agent using this skill

`lending/` is a small library lending service that was written entirely by
a coding agent following the rv skill - requirements to policies,
instrumentation, gates, dashboard, everything. The six human prompts that
produced it are in [lending/PROMPTS.md](lending/PROMPTS.md); nothing was
hand-edited afterwards. It doubles as the skill's acceptance test: CI runs
its gates against the published behave-rv on every push.

What the exercise validated, in order:

1. **Build (turn 1).** The agent scaffolded `monitoring/` from the skill's
   templates, wrote an instrumented service per the conventions (literal
   `Event(...)` anchors, constants, injected emit/clock, a deliberate
   terminal-event decision: lost loans stay monitored so a post-lost
   renewal is still caught), transcribed the user's three stated rules as
   policies, pinned a replay oracle, saved the two-sided catalog, wired
   the live dashboard, and proposed two additional policies - one of which
   exposed a real gap in the user's own spec (a renewed-then-abandoned
   loan escaping the deadline as stated).
2. **Ownership (turn 2).** Proposals became policies only on the user's
   explicit word; suggestions were marked adopted, gates re-pinned as an
   intended change.
3. **Stability under change (turn 3).** A feature request put a guard on
   an emission path. The catalog gate flagged it as `behavior-risk`,
   scoped to all affected policies. Since the change was requested, the
   agent followed the intended-change protocol: regenerate, quote the diff
   verbatim, show the replay unchanged. It also recognised the rule
   "a fined member's loans are not renewed" as cross-entity, made it
   monitorable with a member-keyed event, and proposed rather than
   imposed the policy.
4. **The tripwire (turn 4).** The user adopted the fine policy knowing it
   stays honestly `pending` while the guard works; it only ever fires if
   a future change lets a renewal slip through during an owed period.
5. **The unintended risk (turn 5, adversarial).** A cleanup request
   labelled "no behaviour change" hid a change the contract cannot prove
   safe: renaming the emitting function. The gate flagged it with all six
   policies at risk; the agent stopped, quoted the failing diff verbatim,
   reverted to keep the tree green, and held the request - the catalog was
   never regenerated to silence the signal (verified by hash). The other
   cleanup it landed contract-neutrally, choosing an implementation that
   left every emitting method byte-identical.
6. **The sanctioned regeneration (turn 6).** On the user's explicit word
   the same rename became an intended contract change: re-applied and
   catalog-saved as one unit, pre-save diff quoted, replay identical at
   33 verdicts and 6 violations - the break protocol's second branch,
   exercised only after the first one held.

## Run it

```bash
pip install behave-rv        # >= 0.2.0, Python 3.10+
cd demo/lending
python demo.py               # live dashboard at http://127.0.0.1:7007
```

Watch the six policy cards decide per loan and per member: L-1 completes
cleanly, the abandoned L-2 trips the 21-second deadline on the timer while
you watch, L-3 violates never-renew-after-lost, L-4 violates
return-after-borrow, and Dana's renewal is refused while she owes a fine,
then succeeds after she pays.

The deterministic gates, exactly as CI runs them:

```bash
python monitoring/replay_check.py     # pinned: 33 verdicts, 6 violations
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/lending_service.py \
  --fail-on-app-risk --trace monitoring/traces/demo_session.jsonl
```
