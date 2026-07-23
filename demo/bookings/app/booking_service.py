"""Class-booking service for a small fitness studio, born monitorable.

The business logic is ordinary. Beside each state transition it emits one
``Event`` so the runtime monitors can watch a booking's whole life. The
emission is additive: remove every ``self._status(...)`` / terminal line and
the bookings still work exactly the same. ``emit`` and ``clock`` are injected,
so the identical service runs live (real queue, real clock) and under the
deterministic replay gate (a list and a fake clock).

One booking = one record, keyed by ``booking_id`` (e.g. ``"B-1042"``). Its
life: reserved (or waitlisted -> promoted) -> confirmed -> checked_in ->
attended, with cancelled and no_show as alternative endings.

attended, cancelled and no_show all END a booking. But only ``attended`` and
``no_show`` emit the terminal event that retires the monitor: after those,
genuinely nothing can follow. A cancellation deliberately does NOT emit the
terminal - the studio's top rule is to catch a member who cancels and then
still shows up and checks in, and a terminal would retire the monitor before
that check-in could be seen. A cancelled booking is instead reclaimed by the
engine's quiescence TTL, so post-cancellation activity stays observable for
the window that matters. (Its "reached an end state" status still fires, so
the eventual-end policy is satisfied at the cancellation.)
"""

from __future__ import annotations

import time

from behave_rv.events.event import Event

# Event-type identities are module-level constants, referenced by name, so the
# stability analyzer can resolve them (a computed type would go <dynamic>).
EVENT_TYPE = "booking.status"     # one stable type for the whole lifecycle
TERMINAL_TYPE = "booking.done"    # ends a booking's life: settles its policies

# The three states after which nothing more may happen to a booking.
TERMINAL_STATES = ("attended", "cancelled", "no_show")

# Balance state stamped on a confirmation (the member's account at that instant).
BALANCE_CLEAR = "clear"
BALANCE_OWING = "owing"

# Capacity/duplicate flag stamped on a confirmation. The app does the counting
# (per class, per member) that the per-booking monitor cannot, and records its
# verdict here so the monitor can enforce that a flagged booking is never
# confirmed. "none" means the app found nothing wrong.
FLAG_NONE = "none"
FLAG_DUPLICATE = "duplicate"
FLAG_OVER_CAPACITY = "over_capacity"


class BookingService:
    def __init__(self, emit, clock=time.time):
        self._emit = emit          # injected: live queue push, or list.append
        self._clock = clock        # injected: real clock, or a FakeClock

    def _status(self, booking_id, status, member_id, class_id, **extra):
        """Emit one observable status change for a booking."""
        self._emit(Event(
            EVENT_TYPE,
            self._clock(),
            {"booking_id": booking_id},
            {"status": status, "member_id": member_id,
             "class_id": class_id, **extra},
            "booking-service",
        ))

    def _end(self, booking_id, status, member_id, class_id, **extra):
        """Emit a terminal status, then the terminal event that retires it."""
        self._status(booking_id, status, member_id, class_id, **extra)
        # Distinct, strictly-later timestamp so the observable end state is
        # processed before the terminal retires the instance.
        self._emit(Event(
            TERMINAL_TYPE,
            self._clock() + 1e-6,
            {"booking_id": booking_id},
            {"final_status": status, "member_id": member_id,
             "class_id": class_id},
            "booking-service",
        ))

    # --- lifecycle transitions (one tap each) ---------------------------------

    def reserve(self, booking_id, member_id, class_id):
        self._status(booking_id, "reserved", member_id, class_id)

    def waitlist(self, booking_id, member_id, class_id):
        self._status(booking_id, "waitlisted", member_id, class_id)

    def promote(self, booking_id, member_id, class_id):
        """A spot freed: a waitlisted booking becomes reserved."""
        self._status(booking_id, "promoted", member_id, class_id)

    def confirm(self, booking_id, member_id, class_id,
                balance_state=BALANCE_CLEAR, flag=FLAG_NONE):
        """Payment cleared. ``balance_state`` and ``flag`` record what the app
        knew at this instant: whether the member still owed money, and whether
        the app had flagged this booking as a duplicate or over capacity."""
        self._status(booking_id, "confirmed", member_id, class_id,
                     balance_state=balance_state, flag=flag)

    def check_in(self, booking_id, member_id, class_id):
        self._status(booking_id, "checked_in", member_id, class_id)

    def mark_attended(self, booking_id, member_id, class_id):
        self._end(booking_id, "attended", member_id, class_id)

    def cancel(self, booking_id, member_id, class_id):
        # Ends the booking, but emits NO terminal: a post-cancellation check-in
        # must stay visible (see the module docstring). Reclaimed by TTL.
        self._status(booking_id, "cancelled", member_id, class_id)

    def mark_no_show(self, booking_id, member_id, class_id):
        self._end(booking_id, "no_show", member_id, class_id)
