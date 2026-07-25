"""A parcel tracking service. Written long before anyone thought about
monitoring: plain state transitions.

Monitoring was added AFTER the fact and is strictly additive: an injected
``emit`` (default no-op) and ``clock`` (default wall clock) let the service
announce each state transition as an ``Event`` without changing what it does.
Existing callers that construct ``ParcelService()`` keep the original
behaviour exactly - the default emitter drops every event on the floor.
"""

import time
from dataclasses import dataclass, field

from behave_rv.events.event import Event

# Event types are module-level constants so the stability analyzer can resolve
# them by name (a computed/f-string type would degrade to <dynamic>).
STATUS_EVENT = "parcel.status"
SOURCE = "parcel-service"


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

    def register(self, parcel_id: str, destination: str) -> None:
        parcel = Parcel(parcel_id, destination)
        parcel.history.append("registered")
        self.parcels[parcel_id] = parcel
        self._emit(Event(STATUS_EVENT, self._clock(), {"parcel_id": parcel_id},
                         {"status": "registered"}, SOURCE))

    def hub_scan(self, parcel_id: str, hub: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "scanned"
        parcel.hub = hub
        parcel.history.append(f"scanned@{hub}")
        self._emit(Event(STATUS_EVENT, self._clock(), {"parcel_id": parcel_id},
                         {"status": "scanned", "hub": hub}, SOURCE))

    def out_for_delivery(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "out_for_delivery"
        parcel.history.append("out_for_delivery")
        self._emit(Event(STATUS_EVENT, self._clock(), {"parcel_id": parcel_id},
                         {"status": "out_for_delivery"}, SOURCE))

    def deliver(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "delivered"
        parcel.history.append("delivered")
        self._emit(Event(STATUS_EVENT, self._clock(), {"parcel_id": parcel_id},
                         {"status": "delivered"}, SOURCE))

    def route_to(self, parcel_id: str, hub: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "rerouted"
        parcel.hub = hub
        parcel.history.append(f"rerouted@{hub}")
        self._emit(Event(STATUS_EVENT, self._clock(), {"parcel_id": parcel_id},
                         {"status": "rerouted", "hub": hub}, SOURCE))

    def return_to_sender(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "returned"
        parcel.history.append("returned")
        self._emit(Event(STATUS_EVENT, self._clock(), {"parcel_id": parcel_id},
                         {"status": "returned"}, SOURCE))
