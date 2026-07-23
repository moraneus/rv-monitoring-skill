"""The monitorable vocabulary for the library lending service.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

The entity is a loan; the correlation key is ``loan_id``. Every step observes
the ``loan.status`` event and reads its ``status`` payload field.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# the three statuses that settle a borrowed loan (rule 3's response)
SETTLING_STATUSES = frozenset({"renewed", "returned", "lost"})


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a loan is "{status}"',
                      step_id="loan.status.is",
                      event_type="loan.status",
                      correlation_key="loan_id")
    def loan_is(ctx, event, status):
        return (event.type == "loan.status"
                and event.payload.get("status") == status)

    @registry.trigger('a loan is renewed, returned, or reported lost',
                      step_id="loan.status.settled",
                      event_type="loan.status",
                      correlation_key="loan_id")
    def loan_settled(ctx, event):
        return (event.type == "loan.status"
                and event.payload.get("status") in SETTLING_STATUSES)

    @registry.trigger('a member\'s fine is "{status}"',
                      step_id="member.fine.is",
                      event_type="member.fine",
                      correlation_key="member_id")
    def member_fine_is(ctx, event, status):
        return (event.type == "member.fine"
                and event.payload.get("status") == status)

    @registry.trigger('a member renews a loan',
                      step_id="member.renewal.any",
                      event_type="member.renewal",
                      correlation_key="member_id")
    def member_renews(ctx, event):
        return event.type == "member.renewal"

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
