"""A small library lending service, monitorable by construction.

A loan is the entity we care about: a member borrows a book copy (which
starts the loan), may renew it, returns it, or has it reported lost. Each
transition emits an ``Event`` right at its site so behave-rv can verify the
lending rules at runtime. Members can also owe fines; while a member owes
anything, a renewal is refused. Fine transitions and renewals are additionally
emitted keyed by ``member_id`` (key projection) so the fine rule is one
per-member policy rather than a cross-entity one.

Instrumentation notes:
* ``emit`` and ``clock`` are injected so the same service runs live (real
  clock, events to the engine) and under scripted replay (fake clock, events
  into a list) with identical code.
* Event types are module-level constants, referenced by name.
* ``returned`` is the monitor-terminal (a clean, final closure). ``lost`` is
  deliberately NOT a monitor-terminal even though it closes the loan in
  business terms: the "never renew after lost" safety net must stay armed to
  catch an illegal renewal that arrives after the loan was reported lost.
* This service records transitions; it does not itself refuse an out-of-order
  call. The temporal lending rules live in the monitor (the user's policies),
  which is the safety net that catches the code doing the wrong thing.
"""

from __future__ import annotations

import time

from behave_rv.events.event import Event

LOAN_STATUS = "loan.status"        # every loan transition (borrowed/renewed/returned/lost)
LOAN_CLOSED = "loan.closed"        # monitor-terminal: a loan reached a clean final close
MEMBER_FINE = "member.fine"        # a member's fine transition (owed/paid_off), keyed by member
MEMBER_RENEWAL = "member.renewal"  # member-keyed view of a renewal that actually extended a loan

SOURCE = "lending-service"


class LendingService:
    """Drive a library's loans from code; every transition is observable."""

    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock
        self._loans: dict[str, dict] = {}
        self._fines: dict[str, int] = {}   # member_id -> count of outstanding fines

    def borrow(self, loan_id: str, member_id: str, book_copy: str) -> None:
        """A member borrows a book copy: this starts the loan."""
        self._loans[loan_id] = {
            "status": "borrowed",
            "member_id": member_id,
            "book_copy": book_copy,
        }
        self._emit(Event(LOAN_STATUS, self._clock(), {"loan_id": loan_id},
                         {"status": "borrowed", "member_id": member_id,
                          "book_copy": book_copy}, SOURCE))

    def record_fine(self, member_id: str) -> None:
        """Record that a member owes a fine (adds to their outstanding count)."""
        self._fines[member_id] = self._fines.get(member_id, 0) + 1
        self._emit(Event(MEMBER_FINE, self._clock(), {"member_id": member_id},
                         {"status": "owed"}, SOURCE))

    def pay_fine(self, member_id: str) -> None:
        """Record that a member paid off their outstanding fines."""
        self._fines[member_id] = 0
        self._emit(Event(MEMBER_FINE, self._clock(), {"member_id": member_id},
                         {"status": "paid_off"}, SOURCE))

    def _member_owes_fine(self, member_id) -> bool:
        """Whether this member has any outstanding (unpaid) fine."""
        return member_id is not None and self._fines.get(member_id, 0) > 0

    def renew(self, loan_id: str) -> None:
        """Renew an existing loan, extending its term.

        While the borrowing member owes any outstanding fine, the renewal is
        refused and nothing happens - no state change, no event."""
        loan = self._loans.get(loan_id, {})
        member_id = loan.get("member_id")
        if self._member_owes_fine(member_id):
            return  # refused: the member owes a fine, so the loan is not extended
        loan["status"] = "renewed"
        self._loans[loan_id] = loan
        now = self._clock()
        self._emit(Event(LOAN_STATUS, now, {"loan_id": loan_id},
                         {"status": "renewed"}, SOURCE))
        if member_id is not None:
            # member-keyed view of the same renewal (key projection), so
            # "no renewal while fined" is one per-member policy; distinct
            # timestamp keeps ordering unambiguous.
            self._emit(Event(MEMBER_RENEWAL, now + 1e-3, {"member_id": member_id},
                             {"loan_id": loan_id}, SOURCE))

    def return_loan(self, loan_id: str) -> None:
        """Return the book copy: this closes the loan cleanly."""
        loan = self._loans.get(loan_id, {})
        loan["status"] = "returned"
        self._loans[loan_id] = loan
        now = self._clock()
        self._emit(Event(LOAN_STATUS, now, {"loan_id": loan_id},
                         {"status": "returned"}, SOURCE))
        # follow-up terminal at a distinct timestamp so ordering is unambiguous
        self._emit(Event(LOAN_CLOSED, now + 1e-3, {"loan_id": loan_id},
                         {"reason": "returned"}, SOURCE))

    def mark_lost(self, loan_id: str) -> None:
        """Mark the book copy lost: closes the loan in business terms, but
        no monitor-terminal is emitted so a later illegal renewal is caught."""
        loan = self._loans.get(loan_id, {})
        loan["status"] = "lost"
        self._loans[loan_id] = loan
        self._emit(Event(LOAN_STATUS, self._clock(), {"loan_id": loan_id},
                         {"status": "lost"}, SOURCE))
