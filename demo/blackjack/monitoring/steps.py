"""The monitorable vocabulary for the Blackjack table.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

The monitored entity is a *hand* (one round), keyed by ``hand_id``. Several
steps observe the same event type reading different payload fields - that is
one step per condition, not per event type.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a hand is dealt',
                      step_id="hand.dealt.is",
                      event_type="hand.dealt",
                      correlation_key="hand_id")
    def hand_is_dealt(ctx, event):
        return event.type == "hand.dealt"

    @registry.trigger('a card is dealt to the "{to}"',
                      step_id="hand.card.to",
                      event_type="hand.card",
                      correlation_key="hand_id")
    def card_dealt_to(ctx, event, to):
        return event.type == "hand.card" and event.payload.get("to") == to

    @registry.trigger('the hand stands',
                      step_id="hand.stand.is",
                      event_type="hand.stand",
                      correlation_key="hand_id")
    def hand_stands(ctx, event):
        return event.type == "hand.stand"

    @registry.trigger('the "{who}" busts',
                      step_id="hand.bust.who",
                      event_type="hand.bust",
                      correlation_key="hand_id")
    def participant_busts(ctx, event, who):
        return event.type == "hand.bust" and event.payload.get("who") == who

    @registry.trigger('the hand is settled',
                      step_id="hand.settled.is",
                      event_type="hand.settled",
                      correlation_key="hand_id")
    def hand_settled(ctx, event):
        return event.type == "hand.settled"

    @registry.trigger('the hand is settled as a "{outcome}"',
                      step_id="hand.settled.as",
                      event_type="hand.settled",
                      correlation_key="hand_id")
    def hand_settled_as(ctx, event, outcome):
        return (event.type == "hand.settled"
                and event.payload.get("outcome") == outcome)

    @registry.trigger('a hand is resettled',
                      step_id="hand.resettled.is",
                      event_type="hand.resettled",
                      correlation_key="hand_id")
    def hand_resettled(ctx, event):
        return event.type == "hand.resettled"

    @registry.trigger('a payout happens',
                      step_id="hand.payout.is",
                      event_type="hand.payout",
                      correlation_key="hand_id")
    def payout_happens(ctx, event):
        return event.type == "hand.payout"

    @registry.trigger('the hand is closed',
                      step_id="hand.closed.is",
                      event_type="hand.closed",
                      correlation_key="hand_id")
    def hand_closed(ctx, event):
        return event.type == "hand.closed"

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
