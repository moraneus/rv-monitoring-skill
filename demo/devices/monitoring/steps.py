"""The monitorable vocabulary for the IoT fleet tracker.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are PURE: read the event, bind the correlation key, return a
  boolean. No side effects, no I/O.
* One step per CONDITION, not per event type -- several steps may observe the
  same event type reading different fields.
* When rewording a phrasing, keep the old wording as an alias so existing
  policies keep compiling.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # -- device lifecycle: one step, matches any lifecycle state by value.
    #    Used for provisioned / provision_ok / provision_failed / activated /
    #    quarantined / wiped / retired.  Correlation key: device_id.
    @registry.trigger('a device is "{state}"', step_id="device.lifecycle.is",
                      event_type="device.lifecycle", correlation_key="device_id")
    def device_is(ctx, event, state):
        if event.type == "device.lifecycle" \
                and event.payload.get("state") == state:
            ctx.bind(device_id=event.bindings["device_id"])
            return True
        return False

    # -- a device action, matched by its reported result ("ok" | "blocked").
    #    General-purpose vocabulary over the action stream.
    @registry.trigger('a device action is "{result}"',
                      step_id="device.action.is",
                      event_type="device.action", correlation_key="device_id")
    def device_action_is(ctx, event, result):
        if event.type == "device.action" \
                and event.payload.get("result") == result:
            ctx.bind(device_id=event.bindings["device_id"])
            return True
        return False

    # -- a device action that is NOT a blocked rejection. Phrased as an INTENT
    #    (result != "blocked"), not an enumeration of allowed values, so any
    #    future non-blocked result lands INSIDE the rule by being classified,
    #    rather than escaping it by being unlisted. This is the prohibition a
    #    quarantined device must never trip.
    @registry.trigger('a device performs a non-blocked action',
                      step_id="device.action.non_blocked",
                      event_type="device.action", correlation_key="device_id")
    def device_non_blocked_action(ctx, event):
        if event.type == "device.action" \
                and event.payload.get("result") != "blocked":
            ctx.bind(device_id=event.bindings["device_id"])
            return True
        return False

    # -- a sensor feed reading, matched by its status. Correlation key:
    #    sensor_id -- a sensor feed is a SEPARATE entity from any device.
    @registry.trigger('a sensor reading is "{status}"',
                      step_id="sensor.reading.is",
                      event_type="sensor.reading", correlation_key="sensor_id")
    def sensor_reading_is(ctx, event, status):
        if event.type == "sensor.reading" \
                and event.payload.get("status") == status:
            ctx.bind(sensor_id=event.bindings["sensor_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file, in sorted
    order (numbered file names keep the ladder readable and diffs stable)."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
