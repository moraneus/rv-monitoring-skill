"""The application under monitoring: a small fitness-studio class-bookings
service.

This file is the business logic. Monitoring asks almost nothing of it: the
service takes an ``emit`` callable and calls it once per observable state
change. It never imports the engine, never knows about policies, and its logic
is not reshaped to be observable.

Conventions (copied from the behave-rv instrumentation guide):

* ``emit`` and ``clock`` are injected, so the same service runs live (real
  clock, events to the engine) and under the replay gate (fake clock, events
  into a list) identically.
* Event construction is visible at the call site and event types are
  module-level constants, so the stability analyzer can follow the emit sites.

One entity: the individual booking, keyed by ``booking_id`` (e.g. "B-1042").
Its life runs reserved -> [waitlisted -> promoted ->] confirmed -> checked_in
-> attended, with cancelled and no_show as the other endings.

There is deliberately NO terminal event type. attended / cancelled / no_show
are where a booking's story normally ends, but the monitor keeps watching each
booking for a window after its last activity (quiescence TTL) rather than
closing the file the instant it ends. That is what lets the "a cancelled
booking is never checked in" policy still catch a check-in that lands after a
cancellation - the booking's monitor is still alive to see it.
"""

from __future__ import annotations

import time

from behave_rv.events.event import Event

STATUS_TYPE = "booking.status"          # every booking state transition
CAP_TYPE = "booking.cap_exceeded"       # app-side capacity check tripped

CLASS_CAPACITY = 12                     # a class never seats more than this


class BookingService:
    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock
        # the app already counts seats per class to enforce the cap; the
        # monitor never sees this - it only sees the marker event below.
        self._seats: dict[str, set[str]] = {}
        self._class_of: dict[str, str] = {}

    def _status(self, booking_id: str, status: str, **payload) -> None:
        """The tap: one normalized event per state change, nothing more."""
        self._emit(Event(STATUS_TYPE, self._clock(), {"booking_id": booking_id},
                         {"status": status, **payload}, "bookings"))

    # -- the business operations ------------------------------------------

    def reserve(self, booking_id: str, class_id: str = "C-1") -> None:
        self._class_of[booking_id] = class_id
        seats = self._seats.setdefault(class_id, set())
        seats.add(booking_id)
        self._status(booking_id, "reserved", class_id=class_id)
        # the app's own capacity check: if this reservation put the class over
        # the cap, emit a booking-keyed marker a moment later (distinct
        # timestamp) so the monitor can make the slip loud and name the booking.
        if len(seats) > CLASS_CAPACITY:
            self._emit(Event(CAP_TYPE, self._clock() + 1e-3,
                             {"booking_id": booking_id},
                             {"class_id": class_id, "seat_count": len(seats)},
                             "bookings"))

    def waitlist(self, booking_id: str) -> None:
        self._status(booking_id, "waitlisted")

    def promote(self, booking_id: str) -> None:
        self._status(booking_id, "promoted")

    def confirm(self, booking_id: str, balance_owed: bool = False) -> None:
        # payment clears here. The front desk sees the member's balance on the
        # same screen, so we stamp it onto the confirm event: balance_owed True
        # means the booking was confirmed while the member still owed money.
        self._status(booking_id, "confirmed", balance_owed=balance_owed)

    def check_in(self, booking_id: str) -> None:
        self._status(booking_id, "checked_in")

    def mark_attended(self, booking_id: str) -> None:
        self._release_seat(booking_id)
        self._status(booking_id, "attended")

    def cancel(self, booking_id: str) -> None:
        self._release_seat(booking_id)
        self._status(booking_id, "cancelled")

    def mark_no_show(self, booking_id: str) -> None:
        self._release_seat(booking_id)
        self._status(booking_id, "no_show")

    def _release_seat(self, booking_id: str) -> None:
        class_id = self._class_of.get(booking_id)
        if class_id is not None:
            self._seats.get(class_id, set()).discard(booking_id)
