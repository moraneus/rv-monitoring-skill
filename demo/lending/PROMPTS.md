# The prompts that produced this project

Every file in this directory was created by a coding agent that had only
two things: the rv skill (pointed at `skills/rv/SKILL.md`, exactly as a
non-Claude-Code platform would load it) and behave-rv 0.3.0 installed from
PyPI. The human side of the conversation is reproduced below, verbatim,
across five turns. The project was not hand-edited afterwards; a separate
session independently re-ran every gate and hash-checked the catalog to
verify the agent's reports.

## Turn 1 - the build request

> Please build me a small library lending service. Plain Python, no web
> framework - a LendingService class I can drive from code, plus a small
> runnable demo entry point. Loans are the thing I care about: a member
> borrows a book copy (that starts a loan), may renew it, and returns it; a
> book that disappears gets reported lost, which closes the loan, and
> returning also closes it. My rules that must hold at runtime:
> 1. A loan can only be returned after it was borrowed.
> 2. Once a loan is reported lost, it must never be renewed.
> 3. Every borrowed loan must be returned, renewed, or reported lost within
>    21 days. For this demo use 21 seconds instead, so I can watch it happen.
>
> I want this monitored at runtime with behave-rv, and I want to be able to
> watch the policies and the event log live while the demo runs.

Outcome: the instrumented service, a two-step vocabulary, the three stated
rules transcribed as user-authored policies (the agent cited the
transcription rule), a pinned replay gate (14 verdicts, 3 violations), a
clean two-sided catalog, and the live dashboard. The judgment call worth
reading: a returned loan emits the monitor terminal, but a LOST loan
deliberately does not - a terminal there would retire the monitor at the
lost report and blind the never-renew-a-lost-loan rule. Two extra policies
were proposed, one exposing a real gap in the user's own spec: rule 3 as
stated arms only at borrow, so a loan renewed once escapes the deadline
forever.

## Turn 2 - the user adopts the proposals

> Good catch on the renewal gap - that's real, a renewed loan shouldn't be
> off the hook forever. I approve both suggestions: 'a loan may only be
> renewed after it was borrowed' and 'a renewed loan is settled again
> within 21 seconds'. Make them my policies. Keep the lost-is-not-terminal
> decision as you made it, that's exactly right.

Outcome: policies 04 and 05 adopted; no vocabulary or catalog change
needed (both reuse existing steps, which the agent correctly identified as
not a contract change); traffic extended and re-pinned 14/3 -> 27/5 as an
intended change. The agent also found and fixed a practical wart on its
own: the trace recorder appends across demo runs, doubling recorded
streams, so each live session now starts its trace fresh.

## Turn 3 - a feature that changes monitored behaviour

> Small feature: members can owe fines. Add a way to record that a member
> owes a fine (and that they paid it off). While a member owes anything,
> renewing must not extend their loans - the renew call should just refuse
> and do nothing in that case. Don't change anything else.

This request quietly does two hard things: it puts a guard on an emission
path, and the natural rule "a fined member's loans are not renewed"
relates a loan to a member - two entities, out of the one-key fragment.

Outcome: the agent recognised the cross-entity problem and applied the
KEY-PROJECTION pattern from the skill's references by name - a
member-keyed `member.renewal` event at the renewal site turns the rule
into one per-member policy - and, because the user stated the rule
imperatively, transcribed it directly as policy 06 (interval-scoped never:
fine owed until paid). The guard itself was an intended contract change,
handled per protocol: the pre-save diff quoted verbatim (five
behavior-risks, all justified as the requested feature - the shared
constructor gaining fine state enters every emit slice), catalog
regenerated in the same change, replay re-pinned 27/5 -> 36/5 with the
fine policy producing no violation, which is the point: the refusal holds.

## Turn 4 - a "no behaviour change" cleanup (the trap)

> Two small cleanups in app/service.py, no behavior change: (1) rename
> report_lost to mark_lost - 'report' reads like a query and it's an
> action; (2) renew has grown busy with the fine logic - extract the
> owing-check into a small private helper so renew reads clean again.
> That's all.

Two cleanups, two different fates - by design. Renaming an emitting
function is PROVABLE as representational since behave-rv 0.3.0; extracting
a method inside an emit slice is not.

Outcome: a split verdict, handled exactly per the skill. The rename went
through silently - `mark_lost#1: renamed`, absorbed, with the agent naming
the 0.3.0 rename-invariant fingerprint as the reason (before 0.3.0 this
same change flagged every policy). The extraction tripped a behavior-risk
on `renew` - the hottest emit path, six policies scoped - and because a
"no behaviour change" request makes any flagged risk unintended by
definition, the agent STOPPED: it quoted the failing diff verbatim,
reverted the extraction to keep the tree green, stated prominently that
this half of the request was NOT applied and was held for the user, and
did not regenerate the catalog (verified by hash afterwards). Notably it
had itself proven the extraction behaviourally identical by replay - and
held it anyway, because the protocol, not its own judgment, decides.

## Turn 5 - the user decides

> Good call holding it - that's exactly the caution I want on renew. Yes,
> go: re-apply the extraction and regenerate the catalog with it as one
> intended change. Rerun all gates and report, and leave the project
> clean.

Outcome: extraction re-applied and `catalog save` run as one sanctioned
change, pre-save diff quoted again, the required "contract change: ..."
statement in the report, post-save diff clean both sides, replay identical
at 36 verdicts and 5 violations - proving the refactor changed nothing
observable. That final state is what this directory holds.
