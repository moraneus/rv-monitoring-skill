# /rv — the interactive monitoring consultation

Run this interview when invoked as `/rv`. Use the AskUserQuestion tool where
available (batch related questions; offer concrete options plus free text);
otherwise ask in plain prose, a few questions at a time. Skip questions the
codebase already answers — read it first and confirm rather than ask.

## The interview

**1. Entities and identity.** What are the long-lived "things" the system
tracks (orders, users, sessions, jobs, devices)? For each: what uniquely
identifies one (the correlation key), and roughly how many are alive at
once? → keys for step declarations; a composite identity (order + line item)
is one tuple key.

**2. Lifecycles.** For each entity: what states does it move through, in
what legal order, and where does its story END (delivered? closed?
logged-out? never)? → status-event vocabulary, `before`/`previously`
candidates for legal ordering, and the terminal event type (or an explicit
"no terminal — some verdicts stay pending" warning).

**3. Prohibitions.** What must NEVER happen — absolutely, or while some
condition holds ("once cancelled, never shipped"; "while locked, no
actions")? Does the condition ever end (until)? → plain and scoped `never`.

**4. Deadlines and SLAs.** What must happen within a bounded time of what
(assignment SLAs, refund windows, reply times)? Get concrete numbers and
whether they are event-time guarantees. → `within` policies; note the number
is part of the policy the user owns.

**5. Eventualities and invariants.** What must eventually happen in every
lifecycle (every ticket resolved)? What should hold at every observation
(every sync succeeds)? → `has happened` (only meaningful with a terminal or
an accepted forever-pending), `always holds`, `since`.

**6. Priorities and boundaries.** Which of the above would page someone at
3am (do those first)? Anything cross-entity or aggregate ("no user with two
active sessions", "max 3 retries") → state clearly these are out of
fragment, offer the nearest per-entity restatement, and record the original
wish in SUGGESTED_POLICIES.md as future-fragment material.

## The output (before touching code)

Write the plan for the user's approval:

1. **Event vocabulary** — types, binding keys, payload fields, terminal
   events, one line each on when it fires.
2. **Steps** — the phrasings you will register, in the user's domain words.
3. **Draft policies** — grouped by the interview sections, each with a
   one-line rationale; marked as SUGGESTIONS the user will own or reject.
4. **Instrumentation points** — which functions/modules gain emissions.
5. **Gates and the live view** — the catalog + replay wiring, CI if
   wanted, and the dashboard the user will watch (its URL and what it
   shows: policy cards with per-entity verdicts, violation explanations,
   the live event feed, the contract strip).

On approval, execute via the development loop in SKILL.md. The interview's
rejected or out-of-fragment items go to `SUGGESTED_POLICIES.md` with their
status, so nothing the user said is silently dropped.
