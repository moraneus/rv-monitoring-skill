"""The monitorable vocabulary for the IoT fleet tracker.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

Two correlation keys live here: ``device_id`` (the device lifecycle and its
actions) and ``sensor_id`` (the sensor feed). One key per scenario.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # 1. the device lifecycle step: matches any device.status by value
    #    (provisioned, provision_ok, provision_fail, activated, quarantined,
    #    wiped).
    @registry.trigger('a device is "{status}"', step_id="device.status.is",
                      event_type="device.status", correlation_key="device_id")
    def device_is(ctx, event, status):
        if event.type == "device.status" \
                and event.payload.get("status") == status:
            ctx.bind(device_id=event.bindings["device_id"])
            return True
        return False

    # 2. a device action, read by its result ("ok" = allowed, "blocked" =
    #    rejected). Its own event type, distinct from the lifecycle.
    @registry.trigger('a device acts "{result}"', step_id="device.action.result",
                      event_type="device.action", correlation_key="device_id")
    def device_acts(ctx, event, result):
        if event.type == "device.action" \
                and event.payload.get("result") == result:
            ctx.bind(device_id=event.bindings["device_id"])
            return True
        return False

    # 3. retirement: the terminal event. No placeholder - the phrasing is the
    #    whole condition.
    @registry.trigger('a device is retired', step_id="device.retired.is",
                      event_type="device.retired", correlation_key="device_id")
    def device_retired(ctx, event):
        if event.type == "device.retired":
            ctx.bind(device_id=event.bindings["device_id"])
            return True
        return False

    # 4. a sensor reading, read by its status. A different entity: keyed on
    #    sensor_id, not device_id.
    @registry.trigger('a sensor reading is "{status}"',
                      step_id="sensor.reading.is",
                      event_type="sensor.reading", correlation_key="sensor_id")
    def sensor_reading_is(ctx, event, status):
        if event.type == "sensor.reading" \
                and event.payload.get("status") == status:
            ctx.bind(sensor_id=event.bindings["sensor_id"])
            return True
        return False

    # 5. the fleet-level quarantine surge. A THIRD entity: keyed on a singleton
    #    fleet_id. The application computes the concurrent-quarantine count and
    #    emits this event when it crosses the threshold; this step just reports
    #    it. The counting is the app's; the engine's verdict is deterministic
    #    over the emitted event.
    @registry.trigger('a quarantine surge is flagged',
                      step_id="fleet.quarantine.surge",
                      event_type="fleet.quarantine", correlation_key="fleet_id")
    def quarantine_surge(ctx, event):
        if event.type == "fleet.quarantine" \
                and event.payload.get("level") == "surge":
            ctx.bind(fleet_id=event.bindings["fleet_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
