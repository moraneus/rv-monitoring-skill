"""The monitorable vocabulary for the parcel service.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# The statuses that end a parcel's lifecycle (delivered or returned to sender).
FINISHED_STATUSES = ("delivered", "returned")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # The lifecycle step: matches any parcel status by value. Covers
    # "scanned", "out_for_delivery", "delivered", "rerouted", "returned".
    @registry.trigger('the parcel becomes "{status}"',
                      step_id="parcel.status.is",
                      event_type="parcel.status",
                      correlation_key="parcel_id")
    def parcel_is(ctx, event, status):
        if event.type == "parcel.status" and event.payload.get("status") == status:
            ctx.bind(parcel_id=event.bindings["parcel_id"])
            return True
        return False

    # Old wording kept as an alias so existing policies phrased
    # 'a parcel is "..."' keep compiling unchanged (step_id is the identity).
    registry.alias("parcel.status.is", 'a parcel is "{status}"')

    # A second step over the SAME event type, reading the status field but
    # matching a SET of terminal statuses. This lets one obligation cover
    # "delivered OR returned" for the delivery-window deadline.
    @registry.trigger('a parcel is finished',
                      step_id="parcel.status.finished",
                      event_type="parcel.status",
                      correlation_key="parcel_id")
    def parcel_is_finished(ctx, event):
        if event.type == "parcel.status" \
                and event.payload.get("status") in FINISHED_STATUSES:
            ctx.bind(parcel_id=event.bindings["parcel_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
