"""The monitorable vocabulary for the parcel service.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

One correlation key throughout: ``parcel_id``.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# The user's definition of "finished": a parcel that has been delivered or
# returned to sender. Enumerated deliberately - a future final status would
# NOT be classified as finished by this predicate (a blind spot noted to the
# user), which is faithful to the user's stated two-outcome definition.
FINAL_STATUSES = ("delivered", "returned")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a parcel is "{status}"',
                      step_id="parcel.status.is",
                      event_type="parcel.status",
                      correlation_key="parcel_id")
    def parcel_is(ctx, event, status):
        """Matches a single parcel status transition by exact value."""
        return (event.type == "parcel.status"
                and event.payload.get("status") == status)

    @registry.trigger('a parcel is finished',
                      step_id="parcel.status.finished",
                      event_type="parcel.status",
                      correlation_key="parcel_id")
    def parcel_finished(ctx, event):
        """Matches the end of a parcel's journey: delivered or returned."""
        return (event.type == "parcel.status"
                and event.payload.get("status") in FINAL_STATUSES)

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
