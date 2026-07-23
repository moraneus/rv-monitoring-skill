"""The monitorable vocabulary for the studio's class bookings.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``booking.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean, change nothing.
* When rewording a phrasing, keep the old wording as an alias.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

EVENT_TYPE = "booking.status"
KEY = "booking_id"

# States that end a booking's life (see app/booking_service.py).
END_STATES = {"attended", "cancelled", "no_show"}


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # 1. The workhorse: matches any lifecycle state by value. Covers reserved,
    #    waitlisted, promoted, confirmed, checked_in, attended, cancelled,
    #    no_show. Used as When / Then / Given across the policies.
    @registry.trigger('a booking is "{status}"',
                      step_id="booking.status.is",
                      event_type=EVENT_TYPE, correlation_key=KEY)
    def booking_is(ctx, event, status):
        if event.type == EVENT_TYPE and event.payload.get("status") == status:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 2. A confirmation made while the member still owed money. Reads the
    #    balance_state the app stamped on the confirm event.
    @registry.trigger('a booking is confirmed while the member owes money',
                      step_id="booking.confirmed.owing",
                      event_type=EVENT_TYPE, correlation_key=KEY)
    def confirmed_while_owing(ctx, event):
        if (event.type == EVENT_TYPE
                and event.payload.get("status") == "confirmed"
                and event.payload.get("balance_state") == "owing"):
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 3. A confirmation the app had flagged as a duplicate or over-capacity.
    #    The per-booking monitor cannot count; it enforces that the app's own
    #    flag is respected (flag != "none" means the app objected).
    @registry.trigger('a booking is confirmed despite a capacity or duplicate flag',
                      step_id="booking.confirmed.flagged",
                      event_type=EVENT_TYPE, correlation_key=KEY)
    def confirmed_while_flagged(ctx, event):
        if (event.type == EVENT_TYPE
                and event.payload.get("status") == "confirmed"
                and event.payload.get("flag", "none") != "none"):
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 4. Either resolving response to a promotion: the member confirmed (paid)
    #    or cancelled. Used as the obligation of the promotion deadline.
    @registry.trigger('a booking is confirmed or cancelled',
                      step_id="booking.resolution",
                      event_type=EVENT_TYPE, correlation_key=KEY)
    def confirmed_or_cancelled(ctx, event):
        if (event.type == EVENT_TYPE
                and event.payload.get("status") in ("confirmed", "cancelled")):
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 5. The booking reached one of its three end states.
    @registry.trigger('a booking reaches an end state',
                      step_id="booking.ended",
                      event_type=EVENT_TYPE, correlation_key=KEY)
    def booking_ended(ctx, event):
        if (event.type == EVENT_TYPE
                and event.payload.get("status") in END_STATES):
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
