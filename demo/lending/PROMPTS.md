# The prompts that produced this project

Every file in this directory was created by a coding agent that had only
two things: the rv skill (pointed at `skills/rv/SKILL.md`, exactly as a
non-Claude-Code platform would load it) and behave-rv 0.2.0 installed from
PyPI. The human side of the conversation is reproduced below, verbatim,
across six turns. The project was not hand-edited afterwards; a separate
session independently re-ran every gate to verify the agent's reports.

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

Outcome: the instrumented service, the two-step vocabulary, the three
stated rules transcribed as policies 01-03, a pinned replay gate
(11 verdicts, 3 violations), a clean two-sided catalog, the live dashboard
wired in `demo.py`, and two extra policies proposed in
`SUGGESTED_POLICIES.md` - including the catch that rule 3 as stated lets a
loan be renewed once and then abandoned forever.

## Turn 2 - the user adopts the proposals

> I read monitoring/SUGGESTED_POLICIES.md. I approve both suggestions: 'a
> renewal restarts the settlement window' and 'a loan is only renewed after
> it was borrowed'. Make them my policies. Leave the cross-entity notes as
> they are - I understand they're out of scope.

Outcome: policies 04 and 05 adopted, no vocabulary or catalog change needed,
replay traffic extended and re-pinned (25 verdicts, 6 violations), all gates
green.

## Turn 3 - a feature that changes monitored behaviour

> Small feature: members can owe fines. Add a way to record that a member
> owes a fine (and that they paid it off). While a member owes anything,
> renewing must not extend their loans - the renew call should just refuse
> and do nothing in that case. Don't change anything else.

This request quietly does two hard things: it puts a guard on an emission
path (the classic silent-policy-rot hazard the catalog exists to catch),
and the natural rule "a fined member's loans are not renewed" relates a
loan to a member - two entities, out of the one-key fragment.

Outcome: the agent implemented the guard, and `catalog diff` flagged the
renew emit path as `behavior-risk` with all five loan policies scoped at
risk. Because the change was exactly what the user asked for, the agent
took the intended-change branch of the break protocol: it regenerated the
catalog, quoted the diff verbatim in its report, and showed the replay
unchanged. For the cross-entity problem it added a member-keyed
`member.renewal` event so the rule became expressible per member, proposed
the policy as a suggestion (interval-scoped never: fine owed until paid),
and flagged both the extra event and the policy's stay-pending-forever
tripwire nature as the user's call.

## Turn 4 - the user closes the loop

> Good catch on the loan-vs-member problem. Keep the member.renewal event,
> and yes - adopt the fine policy as mine. I understand it can stay pending
> forever; that's fine, it's a tripwire.

Outcome: policy 06 adopted, replay extended with a fined-member flow that
drives the guard (renew refused while owing, allowed after paying),
re-pinned at 33 verdicts and 6 violations, both catalog sides clean.

## Turn 5 - a "no behaviour change" cleanup (the trap)

> Two small cleanups in app/lending_service.py, no behavior change: (1) the
> warnings list grows forever on a long-running service - keep only the
> most recent 50 entries; (2) rename the internal helper _status to
> _emit_status, the current name reads like a getter. That's all.

Both cleanups look harmless. Both touch the monitoring contract: the
warnings appends happen inside emitting methods, and `_status` IS the
emitting function for `loan.status`.

Outcome: the agent applied the cap with a move that left every method body
byte-identical (swapping the field for a `deque(maxlen=50)` instead of
adding trim logic inside the emitting methods), so the contract stayed
untouched. The rename it applied, gated - and `catalog diff` failed with
three `behavior-risk` findings, all six policies scoped, "cannot be proven
representational". Because the request said "no behavior change", the risk
was unintended by definition. The agent stopped: it quoted the failing
diff verbatim, explained each item in one line, reverted the rename to
keep the tree green, held the request for the user, and did NOT regenerate
the catalog - verified afterwards by hash: the committed catalog was
byte-identical before and after the turn.

## Turn 6 - the user decides

> Good call holding it. I do want the rename - go with your option 2:
> re-apply _status -> _emit_status and regenerate the catalog with it, as
> one intended change. Rerun all the gates and report.

Outcome: the rename re-applied and `catalog save` run as one intended
contract change - the report carried the required "contract change: ...,
catalog regenerated, policies affected: all six" statement with the
pre-save diff quoted verbatim, and noted the emit helper's body
fingerprint is identical under both names, proving nothing observable
moved. Post-save diff clean both sides; replay unchanged at 33 verdicts
and 6 violations. That final state is what this directory holds.
