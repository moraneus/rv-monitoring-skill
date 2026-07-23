# Instrumentation conventions (and why the analyzer needs each one)

Instrumentation is ADDITIVE: emit events beside the business logic, never
reshape the logic to be observable. If a function must be rewritten to be
monitored, the instrumentation is wrong.

## The checklist

Apply at every state transition, lifecycle boundary, status change, external
call, and queue interaction:

1. **Construct `Event(...)` directly at the site.** The construction is the
   *anchor* the stability analysis keys on - it must be syntactically
   visible. Do not wrap `Event` construction behind factories the analyzer
   cannot see through.
2. **Event types are module-level string constants**, referenced by name:

   ```python
   EVENT_TYPE = "order.status"
   TERMINAL_TYPE = "order.done"
   ...
   self._emit(Event(EVENT_TYPE, self._clock(), {"order_id": oid},
                    {"status": status}, "order-service"))
   ```

   The analyzer resolves literals and module/class constants; a computed
   type degrades to a `<dynamic>` marker and is reported as an
   analyzability loss.
3. **Bindings and payloads are dict literals with string keys.** Keys are
   contract (the emitted interface); `**splat` forwarding is allowed but
   shows as a declared `<splat>` marker, with the forwarded keys covered
   through the callers' fingerprints instead.
4. **Inject `emit` and `clock`** through the constructor so the same service
   runs live (real clock, events to the engine) and under test (fake clock,
   events into a list) identically:

   ```python
   def __init__(self, emit, clock=time.time):
       self._emit = emit
       self._clock = clock
   ```

   The analyzer follows constructor-assigned state, so this wiring is fully
   inside the dependency slice.
5. **Declare a terminal event** per entity type where a lifecycle genuinely
   ends (`order.done`, `session.end`). It settles pending policies and frees
   monitor state. Entities that never end (a task board) simply have none -
   then avoid proposing `has happened` policies without warning the user
   they can pend forever.
6. **Distinct timestamps for ordered actions.** Equal event times are
   ordered canonically (by content), not by arrival - two emissions whose
   order matters must not share a timestamp. Emit the follow-up at
   `clock() + 1e-3`, or tick a fake clock between actions in scripted
   traffic.
7. **One clock everywhere.** Any timestamp magnitude works live (raw
   `time.time()` included, since behave-rv 0.3.0); what matters is that the
   service, the recorder, and the demo traffic share ONE clock. A
   service-relative clock (`time.time() - start`) keeps dashboards and
   traces readable.
8. **Over-expose.** Emit generously: an unused event costs nothing; a
   missing one is a policy the user can never write. When you deliberately
   skip exposing something, note it in the commit or report so the gap is a
   visible decision.
9. **Record traces.** Tee live streams through
   `TraceRecorder("monitoring/traces/....jsonl", clock=clock)` and close it
   on shutdown - the closing clock-horizon marker makes wall-fired deadline
   verdicts reproducible on replay. Recorded traces feed
   `catalog diff --trace` liveness checks and pre-deployment policy replay.

## What the analyzer follows (so keep changes inside this fragment)

The dependency slice of each emission covers: the emitting function, its
transitive callers, their transitive callees, methods assigning any
`self.<attr>` a slice member reads, module- and class-level constants
referenced, and decorators on slice members. Calls it cannot follow
(injected callables, dynamic dispatch, `getattr`) are DECLARED as
unresolved, never silently skipped. Practical consequences:

- Prefer plain calls and `self.method()` calls over passing functions as
  values on emit paths.
- Keep emission-relevant thresholds as named constants - their values are
  fingerprinted.
- A decorator on an emit-path function is part of the contract; changing it
  flags.
- Function renames on emit paths are absorbed when pure (behave-rv >=
  0.3.0 proves them via the rename-invariant fingerprint); a rename mixed
  into the same change as logic edits flags. Rename in its own change.

## Anti-patterns

- Reshaping business logic to expose state - never.
- Event types built with f-strings or concatenation - `<dynamic>`,
  analyzability lost.
- Sharing one timestamp across ordered emissions - ordering becomes
  content-canonical, `before` policies misread.
- Emitting receipt time instead of event time - deadlines and ordering
  silently wrong under lag.
- Side effects inside step predicates - breaks determinism; predicates read
  the event and return a boolean, nothing else.
