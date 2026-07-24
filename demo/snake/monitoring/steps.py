"""The monitorable vocabulary for the Snake game.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean. Placeholder names in
  the phrasing bind by name to the parameter.
* When rewording a phrasing, keep the old wording as an alias.

Every step is keyed by ``game_id`` - one game session is one monitored entity.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a game is "{status}"', step_id="game.status.is",
                      event_type="game.status", correlation_key="game_id")
    def game_is(ctx, event, status):
        if event.type == "game.status" and event.payload.get("status") == status:
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a move is made', step_id="snake.move.made",
                      event_type="snake.move", correlation_key="game_id")
    def move_is_made(ctx, event):
        if event.type == "snake.move":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a reversal is accepted', step_id="snake.move.reversal",
                      event_type="snake.move", correlation_key="game_id")
    def reversal_is_accepted(ctx, event):
        if event.type == "snake.move" and event.payload.get("reversal_accepted") == "true":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('the snake eats food', step_id="snake.food.eaten",
                      event_type="snake.food", correlation_key="game_id")
    def snake_eats_food(ctx, event):
        if event.type == "snake.food":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('the snake grows', step_id="snake.grow.happened",
                      event_type="snake.grow", correlation_key="game_id")
    def snake_grows(ctx, event):
        if event.type == "snake.grow":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('points are scored', step_id="game.score.made",
                      event_type="game.score", correlation_key="game_id")
    def points_are_scored(ctx, event):
        if event.type == "game.score":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
