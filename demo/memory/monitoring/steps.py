"""The monitorable vocabulary for the Memory pairs game.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

Correlation keys per step:
  * a card ......... ("game_id", "position")  - one card inside one game
  * an attempt ..... "attempt_id"             - one two-card attempt
  * the game ....... "game_id"                - the whole game
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

CARD_KEY = ("game_id", "position")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # -- card events (keyed per card within a game) ---------------------------
    @registry.trigger("a card is flipped",
                      step_id="card.flip.is",
                      event_type="card.flip",
                      correlation_key=CARD_KEY)
    def card_is_flipped(ctx, event):
        return event.type == "card.flip"

    @registry.trigger("a card is matched",
                      step_id="card.matched.is",
                      event_type="card.matched",
                      correlation_key=CARD_KEY)
    def card_is_matched(ctx, event):
        return event.type == "card.matched"

    # -- attempt events (keyed per attempt) -----------------------------------
    @registry.trigger("an attempt is ready",
                      step_id="attempt.pending.is",
                      event_type="attempt.pending",
                      correlation_key="attempt_id")
    def attempt_is_ready(ctx, event):
        return event.type == "attempt.pending"

    @registry.trigger("an attempt is resolved",
                      step_id="attempt.resolved.is",
                      event_type="attempt.resolved",
                      correlation_key="attempt_id")
    def attempt_is_resolved(ctx, event):
        return event.type == "attempt.resolved"

    @registry.trigger('an attempt is resolved as "{outcome}"',
                      step_id="attempt.resolved.outcome",
                      event_type="attempt.resolved",
                      correlation_key="attempt_id")
    def attempt_resolved_as(ctx, event, outcome):
        return (event.type == "attempt.resolved"
                and event.payload.get("outcome") == outcome)

    # -- game lifecycle events (keyed per game) -------------------------------
    @registry.trigger("the game starts",
                      step_id="game.start.is",
                      event_type="game.start",
                      correlation_key="game_id")
    def game_starts(ctx, event):
        return event.type == "game.start"

    @registry.trigger("the game is complete",
                      step_id="game.complete.is",
                      event_type="game.complete",
                      correlation_key="game_id")
    def game_is_complete(ctx, event):
        return event.type == "game.complete"

    @registry.trigger("a game action occurs",
                      step_id="game.action.is",
                      event_type="game.action",
                      correlation_key="game_id")
    def game_action_occurs(ctx, event):
        return event.type == "game.action"

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
