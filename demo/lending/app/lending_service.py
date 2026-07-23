"""A small library lending service, driveable from code.

The service owns loans. A member borrows a book copy (that starts a loan),
may renew it, and returns it; a copy that disappears is reported lost. Both
returning and reporting-lost close the loan operationally; only a return also
frees the monitor (see TERMINAL_TYPE).

Members can also owe fines. While a member owes anything, ``renew`` refuses
and does nothing for that member's loans. Fine state is keyed by member, so
its events carry ``member_id`` (loans carry ``loan_id``); the two are separate
entities.

Monitoring is ADDITIVE here: every state change constructs an ``Event(...)``
right at the site and hands it to an injected ``emit`` callable. The business
logic is never reshaped to be observable - remove the emits and the service
still lends books. ``emit`` and ``clock`` are injected through the
constructor so the exact same service runs live (real queue + wall clock) and
under the deterministic replay gate (a list + a fake clock).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from behave_rv.events.event import Event

# Stable event-type identities (not display names). The stability analyzer
# resolves these module-level constants by name; keep them literal.
EVENT_TYPE = "loan.status"     # every lifecycle state change of a loan
TERMINAL_TYPE = "loan.closed"  # the monitor terminal: a loan is fully done
#
# Only a *return* emits the terminal. A returned loan is finished, so its
# monitor state is freed and its policies settle. A *lost* loan closes
# operationally (``loan.open`` goes False) but deliberately does NOT emit the
# terminal: the monitor must keep watching it to catch an illegal renewal of
# a lost loan (rule 2). A lost loan is instead reclaimed by the engine's
# quiescence TTL once it falls silent.

SOURCE = "lending-service"

# The loan.closed terminal is emitted strictly AFTER its status event so the
# status is processed before the entity settles (equal event times are
# ordered canonically by content, not by arrival).
_EPSILON = 1e-3

# Status values a loan moves through.
BORROWED = "borrowed"
RENEWED = "renewed"
RETURNED = "returned"
LOST = "lost"

# The member-fine surface (a separate entity, keyed by member_id).
FINE_TYPE = "member.fine"            # a member's fine balance changes
MEMBER_RENEWAL_TYPE = "member.renewal"  # a successful renewal, by member
FINE_OWED = "owed"                   # the member now owes something
FINE_PAID = "paid_off"               # the member has cleared their balance


@dataclass
class Loan:
    loan_id: str
    member_id: str
    copy_id: str
    status: str
    open: bool = True


@dataclass
class LendingService:
    """Drive it from code: ``borrow`` / ``renew`` / ``return_loan`` /
    ``report_lost``, plus ``record_fine`` / ``pay_fine`` for member fines.
    Each call performs the operation and emits the matching event beside it.

    The service tracks open loans and logs when an operation looks wrong, but
    it does not silently swallow the action: the physical event (a book handed
    back, a copy declared missing) is real and is always emitted, so the
    runtime monitor - not this bookkeeping - is the authority on the rules.
    The one exception is the fine guard: while a member owes, ``renew`` refuses
    and emits nothing, because the requirement is that the renewal not happen.
    """

    emit: Callable[[Event], None]
    clock: Callable[[], float] = time.time
    loans: dict[str, Loan] = field(default_factory=dict)
    fines: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def _status(self, loan_id: str, status: str, at: float, **payload) -> None:
        self.emit(Event(EVENT_TYPE, at, {"loan_id": loan_id},
                        {"status": status, **payload}, SOURCE))

    def _close(self, loan_id: str, at: float) -> None:
        self.emit(Event(TERMINAL_TYPE, at, {"loan_id": loan_id}, {}, SOURCE))

    def _fine(self, member_id: str, state: str, at: float, **payload) -> None:
        self.emit(Event(FINE_TYPE, at, {"member_id": member_id},
                        {"state": state, **payload}, SOURCE))

    def owes_fine(self, member_id: str) -> bool:
        return self.fines.get(member_id, 0.0) > 0.0

    def borrow(self, loan_id: str, member_id: str, copy_id: str) -> None:
        """A member borrows a copy - this starts the loan."""
        self.loans[loan_id] = Loan(loan_id, member_id, copy_id, BORROWED)
        self._status(loan_id, BORROWED, self.clock(),
                     member_id=member_id, copy_id=copy_id)

    def renew(self, loan_id: str) -> None:
        """Extend an existing loan.

        While the loan's member owes a fine, this refuses and does nothing:
        no state change and no event. (An unknown loan has no known member, so
        the guard cannot apply and the call proceeds as before.)
        """
        loan = self.loans.get(loan_id)
        if loan is not None and self.owes_fine(loan.member_id):
            self.warnings.append(
                f"renew of loan {loan_id} refused: member {loan.member_id} "
                f"owes a fine")
            return
        if loan is None:
            self.warnings.append(f"renew of unknown loan {loan_id}")
        elif not loan.open:
            self.warnings.append(f"renew of closed loan {loan_id}")
        else:
            loan.status = RENEWED
        at = self.clock()
        self._status(loan_id, RENEWED, at)
        if loan is not None:
            # Attribute the successful renewal to the member, so the fine guard
            # is monitorable on the member key (loans use loan_id).
            self.emit(Event(MEMBER_RENEWAL_TYPE, at,
                            {"member_id": loan.member_id},
                            {"loan_id": loan_id}, SOURCE))

    def return_loan(self, loan_id: str) -> None:
        """A copy is handed back - this closes the loan."""
        loan = self.loans.get(loan_id)
        if loan is None:
            self.warnings.append(f"return of loan {loan_id} with no checkout")
        else:
            loan.status = RETURNED
            loan.open = False
        at = self.clock()
        self._status(loan_id, RETURNED, at)
        self._close(loan_id, at + _EPSILON)

    def report_lost(self, loan_id: str) -> None:
        """A copy has disappeared - this closes the loan operationally.

        No terminal is emitted (see TERMINAL_TYPE): the monitor keeps watching
        so an illegal post-lost renewal is still caught.
        """
        loan = self.loans.get(loan_id)
        if loan is None:
            self.warnings.append(f"lost report for unknown loan {loan_id}")
        else:
            loan.status = LOST
            loan.open = False
        self._status(loan_id, LOST, self.clock())

    def record_fine(self, member_id: str, amount: float = 1.0) -> None:
        """Record that a member owes a fine (adds to their balance)."""
        self.fines[member_id] = self.fines.get(member_id, 0.0) + amount
        self._fine(member_id, FINE_OWED, self.clock(),
                   amount=amount, balance=self.fines[member_id])

    def pay_fine(self, member_id: str) -> None:
        """Record that a member paid off what they owe (clears the balance)."""
        self.fines[member_id] = 0.0
        self._fine(member_id, FINE_PAID, self.clock(), balance=0.0)
