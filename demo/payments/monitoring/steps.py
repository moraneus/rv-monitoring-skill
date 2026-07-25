"""The monitorable vocabulary for the payment tracker.

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

# A captured payment must move on to one of these; the set of statuses that
# count as "resolved after capture" for the deadline rule. Named so its value
# is fingerprinted -- a future resolution status added here is a contract change.
_RESOLVED_AFTER_CAPTURE = ("disputed", "closed")

# New charge activity on a payment. Rule 1 forbids these after a dispute: a
# frozen payment must not be re-authorized or re-captured. Named so its value
# is fingerprinted -- a future charge-like status added here is a contract change.
_CHARGE_STATUSES = ("authorized", "captured")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a payment is "{status}"',
                      step_id="payment.status.is",
                      event_type="payment.status",
                      correlation_key="payment_id")
    def payment_status_is(ctx, event, status):
        return (event.type == "payment.status"
                and event.payload.get("status") == status)

    @registry.obligation('a payment changes status',
                         step_id="payment.status.any",
                         event_type="payment.status",
                         correlation_key="payment_id")
    def payment_changes_status(ctx, event):
        # Any lifecycle status transition, regardless of the concrete status.
        return event.type == "payment.status"

    @registry.trigger('a payment is disputed or closed',
                      step_id="payment.status.resolved",
                      event_type="payment.status",
                      correlation_key="payment_id")
    def payment_is_resolved(ctx, event):
        return (event.type == "payment.status"
                and event.payload.get("status") in _RESOLVED_AFTER_CAPTURE)

    @registry.obligation('a payment is authorized or captured',
                         step_id="payment.status.charge",
                         event_type="payment.status",
                         correlation_key="payment_id")
    def payment_is_charge_activity(ctx, event):
        return (event.type == "payment.status"
                and event.payload.get("status") in _CHARGE_STATUSES)

    @registry.trigger('a disputed payment closes',
                      step_id="payment.dispute_closed.is",
                      event_type="payment.dispute_closed",
                      correlation_key="payment_id")
    def disputed_payment_closes(ctx, event):
        return event.type == "payment.dispute_closed"

    @registry.scope('a payment becomes frozen',
                    step_id="payment.frozen.mark",
                    event_type="payment.frozen",
                    correlation_key="payment_id")
    def payment_becomes_frozen(ctx, event):
        return event.type == "payment.frozen"

    @registry.trigger('a payment is frozen-rejected',
                      step_id="payment.rejected.frozen",
                      event_type="payment.rejected",
                      correlation_key="payment_id")
    def payment_frozen_rejected(ctx, event):
        return (event.type == "payment.rejected"
                and event.payload.get("reason") == "frozen")

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
