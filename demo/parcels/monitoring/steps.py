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

# The two statuses that end a parcel's life (matches app.parcel_service).
_FINAL_STATUSES = {"delivered", "returned"}


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # 1. the lifecycle step: matches any single status by value. Covers
    #    scanned, out_for_delivery, delivered, rerouted, returned - used as
    #    When (trigger), Then (obligation/prohibition), or Given (scope).
    @registry.trigger('the parcel becomes "{status}"',
                      step_id="parcel.status.is",
                      event_type="parcel.status",
                      correlation_key="parcel_id")
    def parcel_is(ctx, event, status):
        if event.type == "parcel.status" and event.payload.get("status") == status:
            ctx.bind(parcel_id=event.bindings["parcel_id"])
            return True
        return False

    # 2. the disjunctive delivery-outcome step over the SAME event type: true
    #    when the parcel reached EITHER final status. A single pure predicate,
    #    so "delivered OR returned within 12s" stays one in-fragment obligation.
    @registry.trigger('the parcel becomes delivered or returned',
                      step_id="parcel.status.settled",
                      event_type="parcel.status",
                      correlation_key="parcel_id")
    def parcel_settled(ctx, event):
        if event.type == "parcel.status" \
                and event.payload.get("status") in _FINAL_STATUSES:
            ctx.bind(parcel_id=event.bindings["parcel_id"])
            return True
        return False

    # Prior wordings kept as aliases so every already-written policy still
    # compiles verbatim (policies bind to step_id, not to the phrasing text).
    registry.alias("parcel.status.is", 'a parcel is "{status}"')
    registry.alias("parcel.status.settled", 'a parcel is delivered or returned')

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
