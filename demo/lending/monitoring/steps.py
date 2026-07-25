"""The monitorable vocabulary for the library lending service.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

The correlation key is ``loan_id``: one monitor instance per loan.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# Statuses that end or extend a loan's active phase. Listing these here (and in
# the app) is contract: a status added later that should also "settle" a loan
# must be added to this set, or rule 3 will silently not count it.
SETTLING_STATUSES = {"returned", "renewed", "lost"}


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a loan is "{status}"',
                      step_id="loan.status.is",
                      event_type="loan.status",
                      correlation_key="loan_id")
    def loan_is(ctx, event, status):
        return (event.type == "loan.status"
                and event.payload.get("status") == status)

    @registry.trigger('a loan is returned, renewed, or reported lost',
                      step_id="loan.status.settled",
                      event_type="loan.status",
                      correlation_key="loan_id")
    def loan_settled(ctx, event):
        return (event.type == "loan.status"
                and event.payload.get("status") in SETTLING_STATUSES)

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
