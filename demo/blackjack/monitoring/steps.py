"""The monitorable vocabulary for the Blackjack table.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity; policies bind to it across renames.
  Never reuse one for a different meaning.
* Predicates are PURE: read the event, return a boolean. Nothing else.
* When rewording a phrasing, keep the old wording as an alias.

Every step observes events keyed by ``hand_id`` - one dealt hand is one
monitored entity.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('the hand is dealt a card', step_id="hand.dealt.card",
                      event_type="hand.dealt", correlation_key="hand_id")
    def hand_dealt(ctx, event):
        return event.type == "hand.dealt"

    @registry.trigger('the hand stands', step_id="hand.stood",
                      event_type="hand.stood", correlation_key="hand_id")
    def hand_stood(ctx, event):
        return event.type == "hand.stood"

    @registry.trigger('the hand busts', step_id="hand.busted",
                      event_type="hand.busted", correlation_key="hand_id")
    def hand_busted(ctx, event):
        return event.type == "hand.busted"

    @registry.trigger('the hand is settled', step_id="hand.settled.any",
                      event_type="hand.settled", correlation_key="hand_id")
    def hand_settled(ctx, event):
        return event.type == "hand.settled"

    @registry.trigger('the hand is settled as "{outcome}"',
                      step_id="hand.settled.outcome",
                      event_type="hand.settled", correlation_key="hand_id")
    def hand_settled_as(ctx, event, outcome):
        return (event.type == "hand.settled"
                and event.payload.get("outcome") == outcome)

    @registry.trigger('a payout is made for the hand', step_id="hand.payout",
                      event_type="hand.payout", correlation_key="hand_id")
    def hand_payout(ctx, event):
        return event.type == "hand.payout"

    # rephrasings stay writable so existing policies keep compiling:
    registry.alias("hand.stood", 'the player stands')
    registry.alias("hand.busted", 'the hand goes bust')
    registry.alias("hand.dealt.card", 'a card is dealt to the hand')

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
