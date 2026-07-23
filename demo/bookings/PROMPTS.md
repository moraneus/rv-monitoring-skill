# The prompts that produced this project

This demo tests the /rv INTERACTIVE CONSULTATION: interview first, then a
written plan for approval, and code only on the user's go. Everything here
was created by a coding agent that had only the rv skill and behave-rv
0.3.0 from PyPI; it wrote not a single file until the go-ahead (verified
on disk at every stage). The human side is verbatim below; a separate
session independently re-ran every gate.

## Turn 1 - the invocation

> /rv - I run a small fitness studio and I want runtime monitoring for my
> class bookings. Interview me.

The agent opened with a plain-words framing of what would be built, the
per-entity ground rule stated honestly upfront ("it cannot natively check
rules that compare across many bookings - tell me anyway and I'll offer
the closest per-booking version"), and one structured pass over all six
questionnaire areas: entities and identity, lifecycle and endings,
prohibitions, deadlines, eventualities, and the 3am priorities.

## Turn 2 - the studio owner's answers

> It's the individual booking I care about - one member, one class, one
> spot. Every booking is its own record with a booking id like B-1042.
> Busy day maybe 80 open at once.
>
> Normal life: a member reserves a spot. If the class is full it sits
> waitlisted and can get promoted to reserved when a spot frees up. We
> confirm reserved bookings once payment clears. At the studio the member
> checks in, and after the class we mark it attended. Members can cancel
> any time before check-in. If someone was confirmed but never showed up,
> after the class we mark it no_show. Once it's attended, cancelled or
> no_show, that's it - nothing ever happens to that booking again.
>
> Never happen, in order of how much I care: a cancelled booking later
> getting checked in (that's the nightmare); anyone checked in without
> being confirmed first; and a member who has an unpaid balance getting a
> booking confirmed before they settle it. Also two wishes I know are the
> counting kind you warned about: no member should hold two spots in the
> same class, and a class should never go over 12 people. Do what you can
> and be straight with me about the rest.
>
> One deadline matters: when a waitlisted booking gets promoted, the
> member must confirm (pay) or cancel within 15 seconds - that's demo
> scale, in real life it's 24 hours. Yes, real wall-clock.
>
> Eventually: every booking should reach one of the three end states. If
> that one can only ever be a 'still waiting' light rather than a hard
> alarm, that's fine, but tell me that in the plan.
>
> 3am: the cancelled-then-checked-in rule, and the promotion deadline.

The agent produced the written plan - still no code: an event-vocabulary
table, the step phrasings, six policies marked as the user's own
(transcription), suggestions kept separate, and honest triage of the three
wishes. The unpaid-balance rule was brought in-fragment by KEY PROJECTION
- it is really about the member, so it becomes a member-keyed
interval-scoped never (`Given a member's balance is "owed" until ...
"settled" / Then a member confirms a booking never happens`) with the
extra member-keyed events flagged for veto. The two counting wishes were
refused as out of fragment ("not faking it"), with a partial composite-key
echo offered as a suggestion. The eventually-resolves rule was spelled out
as a green/amber light that can never alarm, with a deadline upgrade
offered as a separate suggestion. The plan ended with exactly two
decisions for the user.

## Turn 3 - the go

> Go. The two decisions: (1) P3 member-keyed is exactly right - keep the
> extra member-level events, the unpaid-balance rule really is about the
> member. (2) P5 ships as the still-waiting light as-is; skip S1 for now.
> One more: take the first half of S3 - attended only after checked_in -
> as my policy too (sloppy front-desk marking is a real thing here); leave
> the promoted-after-waitlisted half and S2 as suggestions.
>
> Build it, run your gates, and give me the demo.

Outcome: the instrumented booking service, six steps, six user-owned
policies, the remaining suggestions parked, gates green with the replay
pinned at 43 verdicts and 5 violations - one clean catch per seeded fault,
including the promotion deadline fired by the engine's own timer. The
instrumentation decision worth reading, made unprompted for the third
time across these demos: `attended` and `no_show` emit the terminal, but
`cancelled` deliberately does not - a hard terminal at cancellation would
retire the monitor before a post-cancellation check-in could be seen, and
catching exactly that was the user's number one rule.
