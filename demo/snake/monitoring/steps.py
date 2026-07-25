"""The monitorable vocabulary for the Snake game.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI detects
  and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies bind
  to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean. Placeholder names in a
  phrasing match the predicate's parameter names (call-by-name).
* One correlation key per scenario: ``game_id``.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

# Straight-reversal detection reads the raw heading fields rather than trusting
# a precomputed flag, so a corrupted move event cannot hide a 180 turn.
_OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a game is "{status}"',
                      step_id="game.status.is",
                      event_type="game.status",
                      correlation_key="game_id")
    def game_status_is(ctx, event, status):
        return (event.type == "game.status"
                and event.payload.get("status") == status)

    @registry.trigger('the snake moves',
                      step_id="game.move.any",
                      event_type="game.move",
                      correlation_key="game_id")
    def snake_moves(ctx, event):
        return event.type == "game.move"

    @registry.trigger('the snake reverses into itself',
                      step_id="game.move.reversal",
                      event_type="game.move",
                      correlation_key="game_id")
    def snake_reverses(ctx, event):
        if event.type != "game.move":
            return False
        d = event.payload.get("direction")
        p = event.payload.get("prev_direction")
        return p is not None and _OPPOSITE.get(d) == p

    @registry.trigger('a point is scored',
                      step_id="game.food.scored",
                      event_type="game.food",
                      correlation_key="game_id")
    def point_scored(ctx, event):
        return event.type == "game.food"

    # rephrasing of the same condition stays compatible via an alias:
    registry.alias("game.food.scored", 'food is eaten')

    @registry.trigger('the snake grows',
                      step_id="game.grow.happens",
                      event_type="game.grow",
                      correlation_key="game_id")
    def snake_grows(ctx, event):
        return event.type == "game.grow"

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
