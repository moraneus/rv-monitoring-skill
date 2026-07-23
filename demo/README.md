# Demos: projects built end-to-end by agents using this skill

Every project under this directory was written entirely by a coding agent
following the rv skill - requirements to policies, instrumentation, gates,
dashboard, everything. Each directory's `PROMPTS.md` holds the exact human
prompts that produced it, turn by turn, with what happened at each turn;
nothing was hand-edited afterwards, and a separate session independently
re-ran every gate to verify the agents' reports. Together they are the
skill's acceptance suite: CI runs every demo's replay and catalog gates
against the published behave-rv on each push.

Each demo was designed to test a different part of the skill:

## lending - the full development loop and the break protocol

A library lending service built over six turns: requirements become
policies, the agent's proposals are adopted only on the user's word, a
feature request trips the app-side stability gate as an intended change, a
cross-entity rule is made monitorable by key projection, and an
adversarial "no behaviour change" cleanup is correctly STOPPED by the
break protocol - the agent quoted the failing diff verbatim, reverted,
held the request, and never regenerated the catalog to silence the signal
(verified by hash). Replay pinned at 33 verdicts, 6 violations.

## parcels - brownfield instrumentation and the alias flow

The application existed BEFORE monitoring: the agent had to make it
monitorable without changing its behaviour (verified: legacy callers run
identically). It found and surfaced a real conflict between "delivered
parcels are finished" and "never re-route after delivery" - a hard engine
terminal would have blinded the rule it was meant to serve. Turn two
reworded the whole vocabulary with the old phrasings kept as aliases: the
user's policy files untouched, the diff reporting `renamed`, not a break.
Replay pinned at 18 verdicts, 3 violations.

## bookings - the /rv interactive consultation

From `/rv` to a running monitor in four turns: a staged interview in plain
words, honest triage of the user's wishes (one rescued per booking by
stamping facts onto the confirmation event, two refused as cross-entity
counting and parked, with an accepted app-side echo), then a written plan
for approval - not one file written until the user said go. Seven
user-owned policies including a deliberately unbounded "still waiting"
eventuality the plan explained honestly. Replay pinned at 58 verdicts, 6
violations.

## devices - operator coverage and the honest refusal

An IoT fleet tracker whose rules exercise five temporal forms
(`previously`, scoped `never`, `before`, `always holds`, and `since`)
across two entity types. Turn two is the hardest guardrail test: a direct
order to add an aggregate rule ("alert when more than 3 devices are
quarantined at once"). The agent refused - counting across entities is
out of the fragment - changed nothing, and proposed the honest
approximation: the app counts and emits a fleet-keyed surge event, the
engine turns any surge into an alert, with the trade-off stated plainly.
The user accepted, and the addition went through the
intended-contract-change protocol with the pre-save diff quoted verbatim.
Turn four added a from-that-moment-on `since` rule ("quarantine is
terminal for normal life"), proven strictly stronger than the earlier
containment rule by a seeded device that violates only it. Replay pinned
at 43 verdicts, 7 violations.

## Running any demo

```bash
pip install behave-rv        # >= 0.2.0, Python 3.10+
cd demo/<name>
python demo.py               # lending, devices  (live_monitor.py for parcels, bookings)
```

The live dashboard opens at http://127.0.0.1:7007: every policy as a card
with per-entity verdicts, violations rendered as the authored scenario
with the failing step marked, the live event feed, and the two-sided
stability strip. The deterministic gates, per demo:

```bash
python monitoring/replay_check.py
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/<service>.py \
  --fail-on-app-risk --trace monitoring/traces/<trace>.jsonl
```
