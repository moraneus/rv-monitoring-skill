"""The monitorable surface for the studio's class bookings: the vocabulary the
studio owner writes policies in.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory returning a fresh
  registry; the behave-rv CLI detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* The ``{status}`` / ``{state}`` placeholders bind BY NAME to the predicate
  parameter of the same name - renaming that parameter disconnects every
  policy that uses the step, and the catalog diff will say so.
* Predicates are pure: read the event, bind the correlation key, return a
  boolean. No side effects.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# Final states after which a booking's story ends.
FINAL_STATES = ("attended", "cancelled", "no_show")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # 1. the booking lifecycle step: matches any status by value. This is the
    #    workhorse behind most policies (reserved / waitlisted / promoted /
    #    confirmed / checked_in / attended / cancelled / no_show).
    @registry.trigger('a booking is "{status}"', step_id="booking.status.is",
                      event_type="booking.status", correlation_key="booking_id")
    def booking_is(ctx, event, status):
        if event.type == "booking.status" and event.payload.get("status") == status:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 2. "reaches a final state": true at attended, cancelled, or no_show. The
    #    disjunction the eventual-resolution policy needs (no single status
    #    covers all three).
    @registry.trigger('a booking reaches a final state',
                      step_id="booking.final.reached",
                      event_type="booking.status", correlation_key="booking_id")
    def booking_reaches_final(ctx, event):
        if event.type == "booking.status" \
                and event.payload.get("status") in FINAL_STATES:
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 3. "confirmed or cancelled": the two acceptable responses to a promotion
    #    (pay, or decline). Used by the promotion-deadline policy.
    @registry.trigger('a booking is confirmed or cancelled',
                      step_id="booking.promo.answered",
                      event_type="booking.status", correlation_key="booking_id")
    def booking_confirmed_or_cancelled(ctx, event):
        if event.type == "booking.status" \
                and event.payload.get("status") in ("confirmed", "cancelled"):
            ctx.bind(booking_id=event.bindings["booking_id"])
            return True
        return False

    # 4. the member's outstanding balance, keyed by MEMBER (not booking): this
    #    is what lets "no confirmation while a balance is owed" be a per-member
    #    rule, since a balance spans a member's bookings.
    @registry.trigger('a member\'s balance is "{state}"',
                      step_id="member.balance.is",
                      event_type="member.balance", correlation_key="member_id")
    def member_balance_is(ctx, event, state):
        if event.type == "member.balance" and event.payload.get("state") == state:
            ctx.bind(member_id=event.bindings["member_id"])
            return True
        return False

    # 5. a member confirms a booking, keyed by MEMBER: the forbidden act inside
    #    the balance-owed window.
    @registry.trigger('a member confirms a booking',
                      step_id="member.booking.confirmed",
                      event_type="member.booking_confirmed",
                      correlation_key="member_id")
    def member_confirms_booking(ctx, event):
        if event.type == "member.booking_confirmed":
            ctx.bind(member_id=event.bindings["member_id"])
            return True
        return False

    # 6. a seat confirmation keyed by (member, class): registered so a
    #    double-booking policy (suggestion S2) can compile if the studio adopts
    #    it. No committed policy uses it yet; the event is emitted anyway
    #    (over-expose - an unused event is cheap).
    @registry.trigger('a seat is "confirmed"', step_id="seat.confirmed.is",
                      event_type="seat.confirmed",
                      correlation_key=("member_id", "class_id"))
    def seat_is_confirmed(ctx, event):
        if event.type == "seat.confirmed":
            ctx.bind(member_id=event.bindings["member_id"],
                     class_id=event.bindings["class_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file (numbered
    file names keep the ladder readable and diffs stable)."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
