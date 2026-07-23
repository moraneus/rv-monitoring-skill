"""A parcel tracking service. Written long before anyone thought about
monitoring: plain state transitions.

Monitoring was added ADDITIVELY: the state transitions below are untouched;
each one now also emits an ``Event`` beside the existing history append. The
``emit`` and ``clock`` collaborators are injected and default to a no-op and
the wall clock, so every existing caller (``ParcelService()``) behaves exactly
as before.

Note: delivery/return are the business end of a parcel's life, but they are
NOT monitoring-terminal events. Rule "a delivered parcel is never re-routed"
requires the monitor to keep watching a parcel AFTER delivery, so no terminal
event is emitted; entities are reclaimed by the engine's quiescence TTL.
"""

import time
from dataclasses import dataclass, field

from behave_rv.events.event import Event

EVENT_TYPE = "parcel.status"     # one stable type for the whole parcel lifecycle


@dataclass
class Parcel:
    parcel_id: str
    destination: str
    status: str = "registered"
    hub: str | None = None
    history: list = field(default_factory=list)


class ParcelService:
    def __init__(self, emit=None, clock=time.time):
        self.parcels: dict[str, Parcel] = {}
        self._emit = emit if emit is not None else (lambda event: None)
        self._clock = clock

    def register(self, parcel_id: str, destination: str) -> None:
        parcel = Parcel(parcel_id, destination)
        parcel.history.append("registered")
        self.parcels[parcel_id] = parcel
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": "registered", "destination": destination},
                         "parcel-service"))

    def hub_scan(self, parcel_id: str, hub: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "scanned"
        parcel.hub = hub
        parcel.history.append(f"scanned@{hub}")
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": "scanned", "hub": hub}, "parcel-service"))

    def out_for_delivery(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "out_for_delivery"
        parcel.history.append("out_for_delivery")
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": "out_for_delivery"}, "parcel-service"))

    def deliver(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "delivered"
        parcel.history.append("delivered")
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": "delivered"}, "parcel-service"))

    def route_to(self, parcel_id: str, hub: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "rerouted"
        parcel.hub = hub
        parcel.history.append(f"rerouted@{hub}")
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": "rerouted", "hub": hub}, "parcel-service"))

    def return_to_sender(self, parcel_id: str) -> None:
        parcel = self.parcels[parcel_id]
        parcel.status = "returned"
        parcel.history.append("returned")
        self._emit(Event(EVENT_TYPE, self._clock(), {"parcel_id": parcel_id},
                         {"status": "returned"}, "parcel-service"))
