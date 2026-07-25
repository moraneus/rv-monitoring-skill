"""The monitorable surface: the vocabulary the studio owner writes policies in.

Conventions (from the behave-rv steps guide):

* ``build_registry()`` is a side-effect-free factory returning a fresh
  registry, so tools and tests get isolation and the CLI detects it.
* ``step_id`` is stable identity, ``<domain>.<event>.<what>`` - never reused,
  never renamed casually; it is what policies bind to across code renames.
* Placeholders bind BY NAME to parameters, so a ``{status}`` placeholder
  requires a parameter called ``status`` (renaming it is a contract break the
  catalog diff reports).
* Predicates are pure: read the event, return a boolean, change nothing.

Every phrasing here is registered as a trigger predicate; the compiler
assembles the temporal operator from the Given/When/Then position in each
policy, so one predicate can be a When, a Then operand, or a Given scope.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# statuses that end a booking's story (used by the "eventually ends" step).
END_STATES = {"attended", "cancelled", "no_show"}


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # 1. the workhorse: the booking lifecycle, matched by status value.
    @registry.trigger('a booking is "{status}"', step_id="booking.status.is",
                      event_type="booking.status", correlation_key="booking_id")
    def booking_is(ctx, event, status):
        if event.type == "booking.status" \
                and event.payload.get("status") == status:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 2. the confirm event carrying the member's outstanding-balance stamp.
    # A distinct step over the same event type, reading a different field.
    @registry.trigger('a booking is confirmed while the member owes',
                      step_id="booking.status.confirmed_owing",
                      event_type="booking.status", correlation_key="booking_id")
    def confirmed_while_owing(ctx, event):
        if event.type == "booking.status" \
                and event.payload.get("status") == "confirmed" \
                and event.payload.get("balance_owed") is True:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 3. the two allowed answers to a waitlist promotion (confirm or cancel).
    @registry.trigger('a booking is confirmed or cancelled',
                      step_id="booking.status.settled",
                      event_type="booking.status", correlation_key="booking_id")
    def confirmed_or_cancelled(ctx, event):
        if event.type == "booking.status" \
                and event.payload.get("status") in {"confirmed", "cancelled"}:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 4. any of the three end states, as one condition. Phrased over the intent
    # ("reaches an end state") rather than listing values, so it keeps meaning
    # the same thing if the value names ever change.
    @registry.trigger('a booking reaches an end state',
                      step_id="booking.status.ended",
                      event_type="booking.status", correlation_key="booking_id")
    def reaches_end_state(ctx, event):
        if event.type == "booking.status" \
                and event.payload.get("status") in END_STATES:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 5. the app-side capacity marker: the booking that pushed a class over cap.
    @registry.trigger('a booking breaks the class capacity',
                      step_id="booking.cap.exceeded",
                      event_type="booking.cap_exceeded",
                      correlation_key="booking_id")
    def breaks_capacity(ctx, event):
        if event.type == "booking.cap_exceeded":
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature in policies/, one policy per file (numbered file
    names keep the ordering and diffs stable)."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
