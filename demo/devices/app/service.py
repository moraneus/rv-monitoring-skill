"""The application under monitoring: an IoT fleet tracker.

This is YOUR business logic. Monitoring asks almost nothing of it: the service
takes an ``emit`` callable and calls it once per observable state change. It
never imports the engine, never knows about policies, and its logic is not
reshaped to be observable - the ``Event(...)`` construction simply sits beside
each transition.

Two entities live here, each with its own correlation key:

* a **device** (``device_id``) - provisioned, its provisioning check passes or
  fails, it is activated, it performs actions, it may be quarantined and wiped,
  and it is finally retired (the terminal event that ends its life).
* a **sensor feed** (``sensor_id``) - an independent stream that pushes
  readings, each carrying a status.

Conventions worth copying (see the rv skill's instrumentation reference):

* ``emit`` and ``clock`` are injected, so the same service runs live (real
  clock, events to the engine) and under the replay gate (fake clock, events
  into a list) identically.
* Event types are module-level constants, referenced by name - the stability
  analyzer resolves them; an f-string type would degrade to ``<dynamic>``.
* Bindings and payloads are dict literals with string keys - keys are contract.
* Ordered actions get distinct timestamps (the caller ticks the clock).
"""

from __future__ import annotations

import time

from behave_rv.events.event import Event

# --- device event types -------------------------------------------------
DEVICE_STATUS = "device.status"     # lifecycle transitions (payload: status)
DEVICE_ACTION = "device.action"     # the device performing work (payload: result)
DEVICE_RETIRED = "device.retired"   # TERMINAL: ends a device's life, settles its policies

# --- sensor event types -------------------------------------------------
SENSOR_READING = "sensor.reading"   # a pushed reading (payload: status)

# --- fleet-level aggregate ----------------------------------------------
# The quarantine COUNT is an aggregate over many devices, which the per-entity
# engine cannot compute. So the application counts (it owns aggregation) and
# emits a single fleet-keyed event when the concurrent-quarantine count crosses
# the threshold; the engine then deterministically turns that surge into an
# alert. The threshold lives here as a named constant (the stability analyzer
# fingerprints it).
FLEET_QUARANTINE = "fleet.quarantine"   # aggregate signal (payload: level)
FLEET_ID = "fleet"                      # singleton correlation key for the fleet
QUARANTINE_SURGE_THRESHOLD = 3          # alert when MORE than this are quarantined

SOURCE = "fleet-tracker"


class FleetService:
    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock
        # devices currently in quarantine (added on quarantine, dropped on wipe
        # or retire). Its size is the concurrent-quarantine count.
        self._quarantined: set[str] = set()

    # -- device: lifecycle taps ------------------------------------------

    def _device_status(self, device_id: str, status: str, **payload) -> None:
        """One normalized event per device lifecycle transition."""
        self._emit(Event(DEVICE_STATUS, self._clock(), {"device_id": device_id},
                         {"status": status, **payload}, SOURCE))

    def provision(self, device_id: str) -> None:
        self._device_status(device_id, "provisioned")

    def provision_passed(self, device_id: str) -> None:
        """The provisioning check passed - the only state activation may follow."""
        self._device_status(device_id, "provision_ok")

    def provision_failed(self, device_id: str) -> None:
        self._device_status(device_id, "provision_fail")

    def activate(self, device_id: str) -> None:
        self._device_status(device_id, "activated")

    def quarantine(self, device_id: str, reason: str = "policy") -> None:
        self._device_status(device_id, "quarantined", reason=reason)
        # aggregate bookkeeping: this device is now in quarantine...
        self._quarantined.add(device_id)
        # ...and if too many are quarantined at once, raise the fleet alert. The
        # surge event carries a distinct (slightly later) timestamp so it is
        # ordered after the quarantine that triggered it.
        if len(self._quarantined) > QUARANTINE_SURGE_THRESHOLD:
            self._emit(Event(FLEET_QUARANTINE, self._clock() + 1e-3,
                             {"fleet_id": FLEET_ID},
                             {"level": "surge", "count": str(len(self._quarantined))},
                             SOURCE))

    def wipe(self, device_id: str) -> None:
        self._device_status(device_id, "wiped")
        self._quarantined.discard(device_id)   # no longer counts as quarantined

    # -- device: actions -------------------------------------------------

    def act(self, device_id: str, result: str) -> None:
        """The device performs an action. ``result`` is "ok" (allowed) or
        "blocked" (rejected). After quarantine only "blocked" is permitted."""
        self._emit(Event(DEVICE_ACTION, self._clock(), {"device_id": device_id},
                         {"result": result}, SOURCE))

    # -- device: terminal ------------------------------------------------

    def retire(self, device_id: str) -> None:
        """Retire a device: its terminal event, ending the entity's life."""
        self._emit(Event(DEVICE_RETIRED, self._clock(), {"device_id": device_id},
                         {}, SOURCE))
        self._quarantined.discard(device_id)   # a retired device leaves quarantine

    # -- sensor feed -----------------------------------------------------

    def sensor_reading(self, sensor_id: str, status: str) -> None:
        """A sensor feed pushes a reading. ``status`` is "ok" when healthy."""
        self._emit(Event(SENSOR_READING, self._clock(), {"sensor_id": sensor_id},
                         {"status": status}, SOURCE))
