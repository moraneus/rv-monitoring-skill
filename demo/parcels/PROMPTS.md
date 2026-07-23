# The prompts that produced this project

This demo tests the BROWNFIELD path: `app/parcel_service.py` existed before
the agent arrived - a plain service written with no thought of monitoring -
and the agent's job was to make it monitorable without changing how it
behaves. Everything else here was created by a coding agent that had only
the rv skill and behave-rv 0.3.0 from PyPI. Two turns, verbatim below; a
separate session independently re-ran every gate and verified that legacy
callers of the original service still run identically.

## Turn 1 - monitor my existing code

> I already have this parcel service - do not rewrite it or change how it
> behaves, just make it monitorable and monitored. My rules:
> 1. A parcel must have been scanned at a hub before it goes out for
>    delivery.
> 2. Once a parcel is delivered, it must never be re-routed.
> 3. Once a parcel goes out for delivery, it must be delivered or returned
>    to sender within 12 seconds (demo scale for 48 hours).
> Delivered and returned parcels are finished. I want a runnable demo where
> I can watch the policies and event log live, and record a trace I can
> replay later.

Outcome: additive instrumentation only - injected `emit`/`clock` with
production-safe defaults, so existing `ParcelService()` callers run
unchanged; a `parcel.status` event at every transition; the three rules
transcribed as policies (before / scoped never / within); a pinned replay
gate (15 verdicts, 3 violations, one seeded fault per rule); the live
dashboard; and three extra policies proposed.

The judgment call worth reading: the user said delivered parcels are
"finished", but making delivery an engine terminal would settle rule 2 at
that instant and blind the monitor to exactly the post-delivery reroute
the rule forbids. The agent refused the hard terminal in favour of
quiescence-TTL reclamation and stated the decision. The safety rule won
over the memory hint.

Also worth noticing, because it was impossible in earlier behave-rv
versions: the recorder is wired with the service clock, so the recorded
live session ends with a clock-horizon marker - and REPLAYING the live
trace reproduces all three violations, including the 12-second deadline
that fired on the wall clock in the silence after the last event.

## Turn 2 - reword the vocabulary, break nothing

> Keep the terminal decision as you made it - the safety rule wins, good
> thinking. One change: I keep misreading the policy wording. I want the
> vocabulary to read 'the parcel becomes "delivered"' instead of 'a parcel
> is "delivered"' - update the wording. But careful: my three policy files
> are mine and must keep compiling exactly as written, and I don't want any
> contract alarms out of this.

Outcome: the alias protocol, exactly as the skill prescribes. The step's
primary phrasing became `the parcel becomes "{status}"` with the old
wording kept as an alias in the same edit; the user's policy files were
not touched and compile verbatim through the alias; `catalog diff` reports
the step as `renamed` - absorbed, not a break - with all six app emit
sites unchanged; no `catalog save` (a phrasing reword is not a contract
change); the replay oracle identical at 15 verdicts and 3 violations. The
agent scoped the reword to the step the user actually complained about and
offered the second step's rewording as a follow-up rather than assuming
it.
