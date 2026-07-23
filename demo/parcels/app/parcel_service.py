"""A parcel tracking service. Written long before anyone thought about
monitoring: plain state transitions, no events, no hooks.

Monitoring was added additively: ``emit`` and ``clock`` are injected through
the constructor (both default to no-op / wall clock, so every existing caller
- ``ParcelService()`` - behaves exactly as before), and each state transition
emits an ``Event`` beside the unchanged business logic. No transition, status
string, or history entry was altered.
"""

import time
from dataclasses import dataclass, field

from behave_rv.events.event import Event

EVENT_TYPE = "parcel.status"       # one stable type for every lifecycle change
TERMINAL_TYPE = "parcel.finished"  # delivered or returned: the parcel is done


@dataclass
class Parcel:
    parcel_id: str
    destination: str
    status: str = "registered"
    hub: str | None = None
    history: list = field(default_factory=list)


class ParcelService:
    def __init__(self, emit=lambda event: None, clock=time.time):
        self.parcels: dict[str, Parcel] = {}
        self._emit = emit
        self._clock = clock

    def _status(self, parcel_id: str, status: str, **payload) -> None:
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": status, **payload}, "parcel-service"))

    def _finish(self, parcel_id: str) -> None:
        self._emit(Event(TERMINAL_TYPE, self._clock() + 1e-3,
                         {"parcel_id": parcel_id}, {}, "parcel-service"))

    def register(self, parcel_id: str, destination: str) -> None:
        parcel = Parcel(parcel_id, destination)
        parcel.history.append("registered")
        self.parcels[parcel_id] = parcel
        self._status(parcel_id, "registered", destination=destination)

    def hub_scan(self, parcel_id: str, hub: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "scanned"
        parcel.hub = hub
        parcel.history.append(f"scanned@{hub}")
        self._status(parcel_id, "scanned", hub=hub)

    def out_for_delivery(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "out_for_delivery"
        parcel.history.append("out_for_delivery")
        self._status(parcel_id, "out_for_delivery")

    def deliver(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "delivered"
        parcel.history.append("delivered")
        self._status(parcel_id, "delivered")
        self._finish(parcel_id)

    def route_to(self, parcel_id: str, hub: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "rerouted"
        parcel.hub = hub
        parcel.history.append(f"rerouted@{hub}")
        self._status(parcel_id, "rerouted", hub=hub)

    def return_to_sender(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "returned"
        parcel.history.append("returned")
        self._status(parcel_id, "returned")
        self._finish(parcel_id)
