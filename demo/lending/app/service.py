"""The library lending service.

The unit of interest is a *loan*: one member borrowing one book copy. A loan
begins when the copy is borrowed, may be renewed, and ends when the copy is
returned or reported lost.

This service is *monitorable by construction*: every loan state change emits a
normalized ``Event`` at the site of the change (see the rv instrumentation
conventions). The service performs the operation and records what happened; it
does NOT itself enforce the temporal rules the user cares about (return only
after borrow, no renew after lost, settle within the deadline). Those rules
are owned by the behave-rv monitor at runtime, which is the whole point of
runtime verification: the monitor is the safety net that catches a bug in the
operational path rather than trusting the path to be correct. In production the
service would additionally guard these transitions; here we leave the path
permissive so the monitor's verdicts are observable.

``emit`` and ``clock`` are injected so the exact same code runs live (real
clock, events into the engine) and under the deterministic replay gate (fake
clock, events into a list).
"""

from __future__ import annotations

import time
from typing import Callable

from behave_rv.events.event import Event

# Event types are module-level string constants, referenced by name, so the
# stability analyzer can resolve them (a computed/f-string type would degrade
# to <dynamic> and lose analyzability).
LOAN_STATUS = "loan.status"      # one stable type for the whole loan lifecycle

SOURCE = "lending-service"

# Loan lifecycle statuses carried in the event payload.
BORROWED = "borrowed"
RENEWED = "renewed"
RETURNED = "returned"
LOST = "lost"


class LendingService:
    def __init__(self, emit: Callable[[Event], None], clock: Callable[[], float] = time.time):
        self._emit = emit
        self._clock = clock

    def _status(self, loan_id: str, status: str, **payload) -> None:
        """Emit one loan state change. The single tap for the lifecycle."""
        self._emit(Event(LOAN_STATUS, self._clock(), {"loan_id": loan_id},
                         {"status": status, **payload}, SOURCE))

    def borrow(self, loan_id: str, member_id: str, book_copy_id: str) -> None:
        """A member borrows a book copy: this starts the loan."""
        self._status(loan_id, BORROWED, member_id=member_id, book_copy_id=book_copy_id)

    def renew(self, loan_id: str) -> None:
        """Extend an existing loan."""
        self._status(loan_id, RENEWED)

    def return_(self, loan_id: str) -> None:
        """The copy is returned: this closes the loan."""
        self._status(loan_id, RETURNED)

    def report_lost(self, loan_id: str) -> None:
        """The copy is reported lost: this closes the loan."""
        self._status(loan_id, LOST)
