"""The monitorable vocabulary for the library lending service.

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

# Kept in sync with app/lending_service.py.
SETTLING_STATUSES = ("returned", "renewed", "lost")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # 1. the lifecycle step: matches a loan status by value. This is the
    #    whole vocabulary for borrowed / renewed / returned / lost.
    @registry.trigger('a loan is "{status}"',
                      step_id="loan.status.is",
                      event_type="loan.status",
                      correlation_key="loan_id")
    def loan_is(ctx, event, status):
        if event.type == "loan.status" and event.payload.get("status") == status:
            ctx.bind(loan_id=event.bindings["loan_id"])
            return True
        return False

    # 2. the disjunctive settlement step (no placeholder: the phrasing is the
    #    whole condition). Used as the response of the 21-second deadline:
    #    a borrowed loan must be returned, renewed, or reported lost.
    @registry.trigger('a loan is renewed, returned or reported lost',
                      step_id="loan.status.settled_or_renewed",
                      event_type="loan.status",
                      correlation_key="loan_id")
    def loan_settled_or_renewed(ctx, event):
        if event.type == "loan.status" \
                and event.payload.get("status") in SETTLING_STATUSES:
            ctx.bind(loan_id=event.bindings["loan_id"])
            return True
        return False

    # 3. the member-fine state, by value ("owed" / "paid_off"). Keyed by
    #    member_id: fines belong to a member, not to a single loan.
    @registry.trigger('a member\'s fine is "{state}"',
                      step_id="member.fine.is",
                      event_type="member.fine",
                      correlation_key="member_id")
    def member_fine_is(ctx, event, state):
        if event.type == "member.fine" and event.payload.get("state") == state:
            ctx.bind(member_id=event.bindings["member_id"])
            return True
        return False

    # 4. a successful renewal attributed to the member (no placeholder: the
    #    phrasing is the whole condition). Lets a policy relate a member's
    #    fine state to their renewals on the single member_id key.
    @registry.trigger('a member renews a loan',
                      step_id="member.renewal.happened",
                      event_type="member.renewal",
                      correlation_key="member_id")
    def member_renews_a_loan(ctx, event):
        if event.type == "member.renewal":
            ctx.bind(member_id=event.bindings["member_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
