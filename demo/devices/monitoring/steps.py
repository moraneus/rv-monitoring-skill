"""The monitorable vocabulary for the IoT fleet tracker.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

Two entities, two correlation keys: a device (``device_id``) and a sensor feed
(``sensor_id``). No scenario mixes them -- one correlation key per policy.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # A device's state transition / action, read by its status value. Observes
    # device.status, keyed by device_id.
    @registry.trigger('a device is "{status}"',
                      step_id="device.status.is",
                      event_type="device.status",
                      correlation_key="device_id")
    def device_is(ctx, event, status):
        return (event.type == "device.status"
                and event.payload.get("status") == status)

    # "contained" = the only things allowed to happen to a quarantined device:
    # a blocked rejection OR the legitimate decommission wipe. Lets the
    # quarantine -> wipe -> retire path stay clean (rule 2) while still flagging
    # any normal action after quarantine. Observes device.status, keyed device_id.
    @registry.trigger('a device is contained',
                      step_id="device.status.contained",
                      event_type="device.status",
                      correlation_key="device_id")
    def device_contained(ctx, event):
        return (event.type == "device.status"
                and event.payload.get("status") in ("blocked", "wiped"))

    # The device's terminal event: its lifetime ends. Observes device.retired,
    # keyed by device_id. No status field -- retirement is the event itself.
    @registry.trigger('a device is retired',
                      step_id="device.retired",
                      event_type="device.retired",
                      correlation_key="device_id")
    def device_retired(ctx, event):
        return event.type == "device.retired"

    # A reading pushed by a sensor feed, read by its status value. Observes
    # sensor.reading, keyed by sensor_id.
    @registry.trigger('a sensor reading is "{status}"',
                      step_id="sensor.reading.is",
                      event_type="sensor.reading",
                      correlation_key="sensor_id")
    def sensor_reading_is(ctx, event, status):
        return (event.type == "sensor.reading"
                and event.payload.get("status") == status)

    # The singleton fleet-wide quarantine occupancy signal, read by its level.
    # The concurrent count is computed in the application (FleetCounter); this
    # step just observes the fleet event. Observes fleet.quarantine, keyed by
    # fleet_id (a single "fleet" entity).
    @registry.trigger('the fleet quarantine level is "{level}"',
                      step_id="fleet.quarantine.level",
                      event_type="fleet.quarantine",
                      correlation_key="fleet_id")
    def fleet_quarantine_level(ctx, event, level):
        return (event.type == "fleet.quarantine"
                and event.payload.get("level") == level)

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
