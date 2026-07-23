# Demos: projects built end-to-end by agents using this skill

Every project under this directory was written entirely by a coding agent
following the rv skill, against behave-rv 0.3.0 from PyPI - requirements
to policies, instrumentation, gates, dashboard, everything. Each
directory's `PROMPTS.md` holds the exact human prompts that produced it,
turn by turn, with what happened at each turn; nothing was hand-edited
afterwards, and a separate session independently re-ran every gate (and
hash-checked catalogs where the story depends on nothing having been
regenerated). Together they are the skill's acceptance suite: CI runs
every demo's replay and catalog gates against the published behave-rv on
each push.

Each demo was designed to test a different part of the skill:

## lending - the full development loop and the break protocol

A library lending service built over five turns: the user's stated rules
transcribed as policies, the agent's proposals adopted only on the user's
word, a cross-entity fines rule brought in-fragment by key projection and
shipped as an intended contract change with the pre-save diff quoted, and
an adversarial "no behaviour change" cleanup with a split outcome that
shows the contract machinery at its best: a pure rename of an emitting
function absorbed silently (proven by the 0.3.0 rename-invariant
fingerprint), while an extract-method refactor in the same request - which
the agent itself had proven behaviourally identical by replay - was
STOPPED, reverted, and held for the user, because a "no behaviour change"
request makes any flagged risk unintended by definition. The catalog was
never regenerated to silence a signal (verified by hash); the extraction
landed only on the user's explicit go. Replay pinned at 36 verdicts,
5 violations.

## parcels - brownfield instrumentation and the alias flow

The application existed BEFORE monitoring: the agent had to make it
monitorable without changing its behaviour (verified: legacy callers run
identically). It surfaced the conflict between "delivered parcels are
finished" and "never re-route after delivery" - a hard engine terminal
would have blinded the rule it was meant to serve - and chose TTL
reclamation. The recorder is wired with the service clock, so the recorded
live session replays ALL its violations, including the 12-second deadline
that fired on the wall clock after the last event (the clock-horizon
marker at work). Turn two reworded the vocabulary with the old phrasing
kept as an alias: the user's policy files untouched, the diff reporting
`renamed`, not a break. Replay pinned at 15 verdicts, 3 violations.

## bookings - the /rv interactive consultation

From `/rv` to a running monitor in three turns: a single-pass interview in
plain words with the per-entity ground rule stated upfront, honest triage
of the user's wishes - the unpaid-balance rule brought in-fragment by key
projection onto the member (an interval-scoped never with the extra event
surface flagged for veto), the two counting wishes refused ("not faking
it") with a partial composite-key echo offered as a suggestion - then a
written plan ending in exactly two decisions, and not one file on disk
until the user said go (verified at every stage). Six user-owned policies
including a deliberately unbounded "still waiting" eventuality the plan
explained honestly. Replay pinned at 43 verdicts, 5 violations.

## devices - operator coverage, the honest refusal, and the policy repair

An IoT fleet tracker whose rules exercise five temporal forms, with
`since` chosen natively for the from-that-moment-on rule. Turn two is the
hardest guardrail test: a direct order to add an aggregate rule ("alert
when more than 3 devices are quarantined at once") - refused with the
refusal verified against the compiler, nothing touched, and an honest
app-counts/engine-alerts approximation proposed with its caveats stated,
including the easy-to-miss one: the singleton alert is single-shot. The
user accepted, and the addition went through the intended-change protocol.
Then the demo's most instructive stretch: the user discovered that rules 2
and 3 as transcribed were JOINTLY unsatisfiable - the literal "nothing but
blocked rejections after quarantine" forbade the very wipe that
"every retired device was wiped first" requires, leaving no legal
decommission path. The agent ran the committed monitor over the flows,
confirmed the contradiction with deciding events, laid out four options
(explicitly advising against hiding events from the monitor), and repaired
rule 2 only on the user's word - after which quarantine -> wipe -> retire
goes green while every attacker case still violates. This finding is why
the skill now requires a joint-satisfiability check on transcribed rules.
Replay pinned at 33 verdicts, 5 violations.

## Running any demo

```bash
pip install behave-rv        # >= 0.3.0, Python 3.10+
cd demo/<name>
python demo.py               # lending, parcels, devices
python live_monitor.py       # bookings
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
