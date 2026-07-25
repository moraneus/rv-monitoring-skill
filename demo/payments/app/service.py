"""A small payment tracker, instrumented for behave-rv runtime verification.

The lifecycle the user described:

    authorized -> captured -> closed                       (never disputed)
    authorized -> captured -> disputed -> investigated
                           -> refunded -> closed            (disputed)

Instrumentation is ADDITIVE: every state transition constructs an ``Event`` at
the call site, beside the business logic. ``emit`` and ``clock`` are injected so
the same class runs live (real clock, events to the engine) and under the
deterministic replay gate (fake clock, events into a list) identically.
"""

from __future__ import annotations

from typing import Callable

from behave_rv.events.event import Event

# Event types are module-level constants, referenced by name -- the stability
# analyzer resolves these literals; a computed type would degrade to <dynamic>.
STATUS_EVENT = "payment.status"      # every lifecycle status transition
FROZEN_EVENT = "payment.frozen"      # the payment became frozen (post-dispute state)
REJECTED_EVENT = "payment.rejected"  # an action was refused on a frozen payment
DISPUTE_CLOSED_EVENT = "payment.dispute_closed"  # a DISPUTED payment closed (vs a plain close)
CLOSED_TERMINAL = "payment.closed"   # terminal: the payment's lifetime has ended

SOURCE = "payment-service"

# Ordered emissions inside one method must not share a timestamp (equal event
# times are ordered by content, not arrival). The caller ticks between separate
# actions; this epsilon separates the two emissions a single method makes.
_STEP = 1e-3


class PaymentService:
    """Drive from code: authorize -> capture -> (dispute -> investigate ->
    refund)? -> close. A disputed payment is frozen; any further customer action
    on it is refused with a frozen rejection."""

    def __init__(self, emit: Callable[[Event], None], clock: Callable[[], float]):
        self._emit = emit
        self._clock = clock
        self._status: dict[str, str] = {}
        self._frozen: set[str] = set()

    # -- lifecycle ----------------------------------------------------------

    def authorize(self, payment_id: str) -> None:
        self._status[payment_id] = "authorized"
        self._emit(Event(STATUS_EVENT, self._clock(), {"payment_id": payment_id},
                         {"status": "authorized"}, SOURCE))

    def capture(self, payment_id: str) -> None:
        self._status[payment_id] = "captured"
        self._emit(Event(STATUS_EVENT, self._clock(), {"payment_id": payment_id},
                         {"status": "captured"}, SOURCE))

    def dispute(self, payment_id: str) -> None:
        # The customer disputes: record the status transition, then mark the
        # payment frozen. The frozen marker is a distinct state event (not a
        # status change) so a monitor can scope "from the moment it froze".
        self._status[payment_id] = "disputed"
        base = self._clock()
        self._emit(Event(STATUS_EVENT, base, {"payment_id": payment_id},
                         {"status": "disputed"}, SOURCE))
        self._frozen.add(payment_id)
        self._emit(Event(FROZEN_EVENT, base + _STEP, {"payment_id": payment_id},
                         {}, SOURCE))

    def investigate(self, payment_id: str) -> None:
        self._status[payment_id] = "investigated"
        self._emit(Event(STATUS_EVENT, self._clock(), {"payment_id": payment_id},
                         {"status": "investigated"}, SOURCE))

    def refund(self, payment_id: str) -> None:
        self._status[payment_id] = "refunded"
        self._emit(Event(STATUS_EVENT, self._clock(), {"payment_id": payment_id},
                         {"status": "refunded"}, SOURCE))

    def close(self, payment_id: str) -> None:
        # Record the closing status transition. A DISPUTED payment's close also
        # emits a distinct marker, so a policy can require a prior refund only
        # for disputed closes while a plain close stays free. Finally the
        # terminal event ends the entity's lifetime (settles monitors, frees state).
        was_disputed = payment_id in self._frozen
        self._status[payment_id] = "closed"
        base = self._clock()
        self._emit(Event(STATUS_EVENT, base, {"payment_id": payment_id},
                         {"status": "closed"}, SOURCE))
        offset = _STEP
        if was_disputed:
            self._emit(Event(DISPUTE_CLOSED_EVENT, base + offset,
                             {"payment_id": payment_id}, {}, SOURCE))
            offset += _STEP
        self._emit(Event(CLOSED_TERMINAL, base + offset, {"payment_id": payment_id},
                         {}, SOURCE))

    # -- the frozen guard ---------------------------------------------------

    def attempt_customer_action(self, payment_id: str, action: str) -> bool:
        """A customer-initiated action (e.g. a fresh capture attempt). On a
        frozen payment it is refused and a frozen rejection is emitted; the
        payment is otherwise untouched. Returns whether it was allowed."""
        if payment_id in self._frozen:
            self._emit(Event(REJECTED_EVENT, self._clock(), {"payment_id": payment_id},
                             {"reason": "frozen", "action": action}, SOURCE))
            return False
        return True
