# The prompts that produced this project

This demo tests the /rv INTERACTIVE CONSULTATION: interview first, then a
written plan for approval, and code only on the user's go. Everything here
was created by a coding agent that had only the rv skill and behave-rv from
PyPI; it wrote not a single file until turn 4. The human side is verbatim
below; a separate session independently re-ran every gate.

## Turn 1 - the invocation

> /rv - I run a small fitness studio and I want runtime monitoring for my
> class bookings. Interview me.

The agent opened the questionnaire: a plain-words explanation of what would
be built, the per-entity ground rule stated honestly upfront, and round one
of questions - the booking lifecycle, what uniquely identifies a booking,
whether it ends, and whether rules about members (not bookings) matter.

## Turn 2 - lifecycle answers, plus three wishes

> 1. A booking starts when a member reserves a spot. If the class is full
> it sits waitlisted and can get promoted to reserved when a spot frees
> up. We confirm reserved bookings once payment clears. At the studio the
> member checks in, and after the class we mark it attended. Members can
> cancel any time before check-in. If someone was confirmed but never
> showed up, after the class we mark it no_show. Once it's attended,
> cancelled or no_show, that's it - nothing ever happens to that booking
> again.
>
> 2. Every booking is its own record with a booking id, like B-1042. Busy
> day maybe 80 open bookings at once.
>
> 3. Mostly my rules are about single bookings. Three wishes while we're
> here: (a) a member who has an unpaid balance should never get a booking
> confirmed until they settle it; (b) no member should hold two spots in
> the same class; (c) a class should never go over 12 people. Do what you
> can with those and be straight with me about the rest.

The agent recapped the lifecycle for confirmation, then triaged the wishes
honestly: (a) is checkable per booking by stamping the member's balance
state onto the confirmation event at the moment it happens; (b) and (c)
are counting across bookings - out of fragment, refused, parked as future
work - with an offered echo: the app does the counting and flags the
booking, and the monitor enforces that a flagged booking is never
confirmed. Round two asked for the prohibitions, the deadlines with
concrete numbers, the eventualities, and the 3am priorities.

## Turn 3 - the rules

> Lifecycle recap is exactly right. On the wishes: do (a) your way -
> checking at the moment of confirmation is exactly what I mean. And yes,
> take the echo for (b) and (c). Park the real cross-member versions as
> future work like you said.
>
> 4. Never happen, in order: a cancelled booking later getting checked in
> (that's the nightmare); anyone checked in without being confirmed first;
> and the (a) rule - confirmed while owing.
>
> 5. One deadline matters: when a waitlisted booking gets promoted, the
> member must confirm (pay) or cancel within 15 seconds - demo scale, in
> real life it's 24 hours. Yes, real wall-clock.
>
> 6. Yes - every booking should eventually reach one of the three end
> states. If that one can only ever be a 'still waiting' light rather than
> a hard alarm, that's fine, but tell me that in the plan.
>
> 7. 3am priorities: the cancelled-then-checked-in rule, and the promotion
> deadline.

The agent produced the written plan - still no code: the event vocabulary
as a table (with the balance_state and flag facts on the confirmation
event), the step phrasings, six user policies quoted in Gherkin, three of
its own marked as suggestions, the out-of-fragment wishes parked, the
instrumentation points, the gates, and the live view. It flagged P6's
honest limitation (a green/amber light, never a hard red) and asked two
closing questions: P6 as-is or with a hard deadline, and whether any
suggestion should go live.

## Turn 4 - the go

> Go. Two answers to your questions: (1) P6 stays a still-waiting light,
> exactly as you described it. (2) Promote S2 to a live policy -
> attendance without a check-in is sloppy front-desk work and I want it
> watched; leave S1 and S3 as suggestions for now.
>
> Build it all, run your gates, and give me the demo.

Outcome: the instrumented booking service, five steps, seven user-owned
policies (P1-P6 plus the promoted S2), the remaining suggestions parked,
gates green with the replay pinned at 58 verdicts and 6 violations - one
clean catch per rule, including the promotion deadline fired by the wall
clock. The instrumentation decision worth reading: `attended` and
`no_show` emit a terminal event, but `cancelled` deliberately does not -
a hard terminal at cancellation would retire the monitor before a
post-cancellation check-in could be seen, and catching exactly that was
the user's number one rule.
