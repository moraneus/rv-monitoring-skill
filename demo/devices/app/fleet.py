"""The application under monitoring: a tiny IoT fleet tracker.

This file is YOUR business logic. Monitoring asks almost nothing of it: the
service takes an ``emit`` callable and calls it once per observable state
change. It never imports the engine, never knows about policies, and its
logic is not reshaped to be observable (instrumentation is additive).

Two conventions worth copying (see the rv skill's instrumentation reference):

* ``emit`` and ``clock`` are injected, so the SAME service runs live (real
  clock, events flowing to the engine) and under the replay gate (fake clock,
  events collected in a list) with identical behaviour.
* Event times are SERVICE-RELATIVE seconds (the caller passes a clock that
  starts near zero), which keeps traces and dashboards readable.

Two entity types live here, each with its own correlation key:

* a DEVICE, keyed by ``device_id`` -- provisioned, its provision check passes
  or fails, activated, it performs actions, may be quarantined, wiped, and is
  finally retired (retirement is the device's TERMINAL event).
* a SENSOR FEED, keyed by ``sensor_id`` -- an independent stream of readings,
  each carrying a status. A sensor feed has no terminal (it is unbounded).

Event types are module-level constants referenced by name -- the stability
analyzer resolves these literals; an f-string or computed type would degrade
to ``<dynamic>`` and lose analyzability.
"""

from __future__ import annotations

import time

from behave_rv.events.event import Event

# -- device events -----------------------------------------------------------
LIFECYCLE_TYPE = "device.lifecycle"   # provisioned / provision_ok / provision_failed
#                                       / activated / quarantined / wiped / retired
ACTION_TYPE = "device.action"         # an action the device REPORTED (result: ok|blocked)
RETIRED_TYPE = "device.retired"       # TERMINAL: ends a device's life, settles its policies

# -- sensor events -----------------------------------------------------------
READING_TYPE = "sensor.reading"       # one reading from a sensor feed (status)

SOURCE = "fleet"
SENSOR_SOURCE = "fleet-sensors"


class FleetService:
    """Records fleet activity as a normalized event stream. One ``Event(...)``
    per observable state change -- nothing more, nothing reshaped."""

    def __init__(self, emit, clock=time.time):
        self._emit = emit
        self._clock = clock

    # -- devices ------------------------------------------------------------

    def _lifecycle(self, device_id: str, state: str, **payload) -> None:
        """One normalized lifecycle event per device state transition."""
        self._emit(Event(LIFECYCLE_TYPE, self._clock(),
                         {"device_id": device_id},
                         {"state": state, **payload}, SOURCE))

    def provision(self, device_id: str) -> None:
        self._lifecycle(device_id, "provisioned")

    def record_provision_check(self, device_id: str, passed: bool) -> None:
        """The provisioning check result -- 'provision_ok' or 'provision_failed'.
        Activation is only legitimate immediately after 'provision_ok'."""
        self._lifecycle(device_id, "provision_ok" if passed else "provision_failed")

    def activate(self, device_id: str) -> None:
        self._lifecycle(device_id, "activated")

    def perform_action(self, device_id: str, result: str) -> None:
        """Record an action the device REPORTED. ``result`` is what the device
        itself reports: 'ok' when it executed, 'blocked' when it honored a
        quarantine and refused. This method does NOT enforce quarantine -- the
        monitor is the guard that verifies a quarantined device only ever
        reports 'blocked' (a compromised device that reports 'ok' after
        quarantine is exactly what the monitor must catch)."""
        self._emit(Event(ACTION_TYPE, self._clock(),
                         {"device_id": device_id},
                         {"result": result}, SOURCE))

    def quarantine(self, device_id: str) -> None:
        self._lifecycle(device_id, "quarantined")

    def wipe(self, device_id: str) -> None:
        self._lifecycle(device_id, "wiped")

    def retire(self, device_id: str, reason: str = "decommissioned") -> None:
        """End a device's life. The observable state change comes first (so a
        policy can talk about 'retired'), then the TERMINAL event a moment
        later -- ordered actions need distinct timestamps, and the terminal
        must not overtake the status it follows."""
        self._lifecycle(device_id, "retired")
        self._emit(Event(RETIRED_TYPE, self._clock() + 1e-3,
                         {"device_id": device_id},
                         {"reason": reason}, SOURCE))

    # -- sensor feeds -------------------------------------------------------

    def sensor_reading(self, sensor_id: str, status: str) -> None:
        """One reading from a sensor feed. A healthy feed only ever reports
        status 'ok'."""
        self._emit(Event(READING_TYPE, self._clock(),
                         {"sensor_id": sensor_id},
                         {"status": status}, SENSOR_SOURCE))
