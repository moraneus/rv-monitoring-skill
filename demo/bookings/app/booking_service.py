"""The application under monitoring: class bookings for a small fitness studio.

This is the studio's business logic. Monitoring asks almost nothing of it: the
service takes an ``emit`` callable and calls it once per observable state
change. It never imports the engine, never knows about policies, and its logic
is not reshaped to be observable - the ``Event(...)`` taps sit beside the
operations.

Two conventions carried from the behave-rv examples:

* ``emit`` and ``clock`` are injected, so the same service runs live (real
  clock, events flowing to the engine) and under the replay gate (fake clock,
  events collected in a list) with identical behaviour.
* Event times are service-relative seconds when a start-anchored clock is
  passed, which keeps the dashboard timeline and traces readable. (Since
  behave-rv 0.3.0 raw ``time.time()`` also works for wall-clock deadlines; the
  relative clock is a readability choice, not a correctness requirement.)

One monitoring decision worth stating in the code, because it is not obvious:
a booking ends its life at attended, cancelled, or no-show. Of those, only
``attended`` and ``no_show`` emit the terminal ``booking.done`` event that
retires the monitor instance. ``cancel`` deliberately does NOT, because the
studio's most important rule is "a cancelled booking must never be checked in"
- the illegal check-in happens AFTER the cancel, so terminating at the cancel
would blind exactly the rule we most want to catch. Cancelled bookings are
reclaimed by the engine's quiescence timeout instead.
"""

from __future__ import annotations

import time

from behave_rv.events.event import Event

# Event types are module-level constants referenced by name: the stability
# analyzer resolves these literals; an f-string or concatenation would degrade
# to a <dynamic> marker and lose analyzability.
STATUS_TYPE = "booking.status"                 # the booking lifecycle
BALANCE_TYPE = "member.balance"                # a member's outstanding balance
MEMBER_CONFIRM_TYPE = "member.booking_confirmed"  # confirm, keyed by member
SEAT_TYPE = "seat.confirmed"                    # confirm, keyed by (member, class)
TERMINAL_TYPE = "booking.done"                 # retires attended / no-show bookings

SOURCE = "booking-service"


class BookingService:
    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock

    def _status(self, booking_id: str, status: str, **extra) -> None:
        """The tap: one normalized event per booking state change."""
        self._emit(Event(STATUS_TYPE, self._clock(), {"booking_id": booking_id},
                         {"status": status, **extra}, SOURCE))

    # -- booking lifecycle -------------------------------------------------

    def reserve(self, booking_id: str, member_id: str, class_id: str) -> None:
        self._status(booking_id, "reserved", member_id=member_id, class_id=class_id)

    def waitlist(self, booking_id: str) -> None:
        self._status(booking_id, "waitlisted")

    def promote(self, booking_id: str) -> None:
        self._status(booking_id, "promoted")

    def confirm(self, booking_id: str, member_id: str, class_id: str) -> None:
        # the booking-keyed transition the lifecycle policies read...
        self._status(booking_id, "confirmed", member_id=member_id, class_id=class_id)
        # ...plus a member-keyed view of the same act, so "no confirmation while
        # the member owes a balance" can be a per-member rule...
        self._emit(Event(MEMBER_CONFIRM_TYPE, self._clock(), {"member_id": member_id},
                         {"booking_id": booking_id}, SOURCE))
        # ...plus a (member, class)-keyed view, so a double-booking rule can be
        # expressed per member+class pair if the studio adopts it (suggestion S2).
        self._emit(Event(SEAT_TYPE, self._clock(),
                         {"member_id": member_id, "class_id": class_id},
                         {"booking_id": booking_id}, SOURCE))

    def check_in(self, booking_id: str) -> None:
        self._status(booking_id, "checked_in")

    def mark_attended(self, booking_id: str) -> None:
        self._status(booking_id, "attended")
        self._terminate(booking_id)

    def mark_no_show(self, booking_id: str) -> None:
        self._status(booking_id, "no_show")
        self._terminate(booking_id)

    def cancel(self, booking_id: str) -> None:
        # a business-terminal state, but intentionally NOT a monitor-terminal:
        # see the module docstring. No booking.done here.
        self._status(booking_id, "cancelled")

    def _terminate(self, booking_id: str) -> None:
        # the terminal fires a moment AFTER the status it follows: ordered
        # actions need distinct timestamps (equal times are ordered
        # canonically, not by arrival), so the terminal must not overtake the
        # final status.
        self._emit(Event(TERMINAL_TYPE, self._clock() + 1e-3,
                         {"booking_id": booking_id}, {}, SOURCE))

    # -- member balance ----------------------------------------------------

    def incur_balance(self, member_id: str) -> None:
        self._emit(Event(BALANCE_TYPE, self._clock(), {"member_id": member_id},
                         {"state": "owed"}, SOURCE))

    def settle_balance(self, member_id: str) -> None:
        self._emit(Event(BALANCE_TYPE, self._clock(), {"member_id": member_id},
                         {"state": "settled"}, SOURCE))
