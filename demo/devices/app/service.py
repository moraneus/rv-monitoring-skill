"""IoT fleet tracker: devices with a provisioning/activation lifecycle, plus
sensor feeds that push readings. Instrumented for behave-rv: every state
transition and lifecycle boundary constructs an ``Event(...)`` at the call
site, beside the business logic (never reshaping it).

Two entities, two correlation keys:

* a **device** (``device_id``) flows through ``device.status`` events
  (provisioned, provision_ok, activated, acted, quarantined, blocked, wiped)
  and ends at the terminal ``device.retired`` event;
* a **sensor feed** (``sensor_id``) pushes ``sensor.reading`` events carrying a
  reading ``status``.

``emit`` and ``clock`` are injected so the same service runs live (real clock,
events to the engine) and under the replay gate (fake clock, events to a list)
identically.
"""

from __future__ import annotations

import time
from typing import Callable

from behave_rv.events.event import Event

# Event types are module-level constants, referenced by name -- the stability
# analyzer resolves these literals; an f-string here would degrade to <dynamic>.
DEVICE_STATUS = "device.status"       # a device state transition / action
DEVICE_RETIRED = "device.retired"     # terminal: the device's lifetime ends
SENSOR_READING = "sensor.reading"     # one reading pushed by a sensor feed
FLEET_QUARANTINE = "fleet.quarantine"  # singleton fleet-level occupancy signal

SOURCE = "fleet-service"

# Device states carried in the device.status payload.
PROVISIONED = "provisioned"
PROVISION_OK = "provision_ok"
ACTIVATED = "activated"
ACTED = "acted"
QUARANTINED = "quarantined"
BLOCKED = "blocked"
WIPED = "wiped"

# A concurrent-quarantine count strictly above this is a fleet-wide surge.
QUARANTINE_SURGE_THRESHOLD = 3


class FleetCounter:
    """Fleet-wide occupancy of quarantine, computed in application code so the
    per-entity engine never has to count across devices. It tracks the set of
    currently-quarantined devices and emits ONE singleton ``fleet.quarantine``
    surge event on the upward crossing above the threshold (re-arming when the
    count falls back to or below it, so each distinct wave is present in the
    stream). A device leaves the concurrent count when it is wiped or retired.
    """

    def __init__(self, emit: Callable[[Event], None],
                 clock: Callable[[], float]) -> None:
        self._emit = emit
        self._clock = clock
        self._quarantined: set[str] = set()
        self._surging = False

    def quarantine(self, device_id: str) -> None:
        self._quarantined.add(device_id)
        self._recount()

    def cleared(self, device_id: str) -> None:
        """The device is no longer an active quarantined device (wipe/retire)."""
        self._quarantined.discard(device_id)
        self._recount()

    def _recount(self) -> None:
        surge = len(self._quarantined) > QUARANTINE_SURGE_THRESHOLD
        if surge and not self._surging:
            self._emit(Event(FLEET_QUARANTINE, self._clock(), {"fleet_id": "fleet"},
                             {"level": "surge", "count": len(self._quarantined)},
                             SOURCE))
        self._surging = surge


class FleetService:
    def __init__(self, emit: Callable[[Event], None],
                 clock: Callable[[], float] = time.time) -> None:
        self._emit = emit
        self._clock = clock
        # additive: fleet-wide concurrent-quarantine counter (same emit/clock)
        self._fleet = FleetCounter(emit, clock)

    # -- device lifecycle ---------------------------------------------------

    def provision(self, device_id: str) -> None:
        """Register a new device; its provisioning check has not yet run."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": PROVISIONED}, SOURCE))

    def provision_ok(self, device_id: str) -> None:
        """The provisioning check passed."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": PROVISION_OK}, SOURCE))

    def activate(self, device_id: str) -> None:
        """Bring the device online."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": ACTIVATED}, SOURCE))

    def act(self, device_id: str, action: str) -> None:
        """The device performs a normal action."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": ACTED, "action": action}, SOURCE))

    def quarantine(self, device_id: str) -> None:
        """Isolate the device: from here on only blocked rejections are allowed."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": QUARANTINED}, SOURCE))
        self._fleet.quarantine(device_id)      # may emit a fleet surge event

    def blocked(self, device_id: str, action: str) -> None:
        """A rejected action against a device (e.g. one under quarantine)."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": BLOCKED, "action": action}, SOURCE))

    def wipe(self, device_id: str) -> None:
        """Wipe the device's data."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": WIPED}, SOURCE))
        self._fleet.cleared(device_id)         # leaves the concurrent count

    def retire(self, device_id: str) -> None:
        """End the device's lifetime (terminal event)."""
        self._emit(Event(DEVICE_RETIRED, self._clock(), {"device_id": device_id},
                         {}, SOURCE))
        self._fleet.cleared(device_id)         # leaves the concurrent count

    # -- sensor feed --------------------------------------------------------

    def sensor_reading(self, sensor_id: str, status: str, value: float) -> None:
        """One reading pushed by a sensor feed."""
        self._emit(Event(SENSOR_READING, self._clock(), {"sensor_id": sensor_id},
                         {"status": status, "value": value}, SOURCE))
