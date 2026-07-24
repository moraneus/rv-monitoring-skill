"""The monitorable vocabulary for the tic-tac-toe game.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean, change nothing.
* When rewording a phrasing, keep the old wording as an alias.

Every step observes one correlation key: ``game_id`` -- one monitor per game.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

STATUS_TYPE = "game.status"
MOVE_TYPE = "game.move"
ENDED_TYPE = "game.ended"
FINISHED_STATES = ("won", "draw")


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # -- moves -------------------------------------------------------------
    @registry.trigger('a move is made', step_id="game.move.any",
                      event_type=MOVE_TYPE, correlation_key="game_id")
    def move_any(ctx, event):
        if event.type == MOVE_TYPE:
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a move is made by "{player}"', step_id="game.move.byplayer",
                      event_type=MOVE_TYPE, correlation_key="game_id")
    def move_by(ctx, event, player):
        if event.type == MOVE_TYPE and event.payload.get("player") == player:
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    # The alternation predicate: this move's player equals the immediately
    # preceding move's player -- i.e. the same player moved twice in a row.
    # A single-event predicate (over the stamped ``prev_player`` field), so it
    # is checked on EVERY move by the self-contained ``never`` form, unlike the
    # triggered ``previously`` which settles on the first move alone.
    @registry.obligation('the same player moves twice in a row',
                         step_id="game.move.repeat",
                         event_type=MOVE_TYPE, correlation_key="game_id")
    def move_repeat(ctx, event):
        return (event.type == MOVE_TYPE
                and event.payload.get("player") == event.payload.get("prev_player"))

    # -- lifecycle status --------------------------------------------------
    @registry.trigger('a game is finished', step_id="game.status.finished",
                      event_type=STATUS_TYPE, correlation_key="game_id")
    def game_finished(ctx, event):
        if event.type == STATUS_TYPE and event.payload.get("state") in FINISHED_STATES:
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a game is started', step_id="game.status.started",
                      event_type=STATUS_TYPE, correlation_key="game_id")
    def game_started(ctx, event):
        if event.type == STATUS_TYPE and event.payload.get("state") == "started":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a game is won', step_id="game.status.won",
                      event_type=STATUS_TYPE, correlation_key="game_id")
    def game_won(ctx, event):
        if event.type == STATUS_TYPE and event.payload.get("state") == "won":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a game is won by "{player}"', step_id="game.status.wonby",
                      event_type=STATUS_TYPE, correlation_key="game_id")
    def game_won_by(ctx, event, player):
        if (event.type == STATUS_TYPE and event.payload.get("state") == "won"
                and event.payload.get("winner") == player):
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    @registry.trigger('a game is a draw', step_id="game.status.draw",
                      event_type=STATUS_TYPE, correlation_key="game_id")
    def game_draw(ctx, event):
        if event.type == STATUS_TYPE and event.payload.get("state") == "draw":
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    # -- terminal ----------------------------------------------------------
    @registry.trigger('a game ends as "{outcome}"', step_id="game.ended.outcome",
                      event_type=ENDED_TYPE, correlation_key="game_id")
    def game_ended_as(ctx, event, outcome):
        if event.type == ENDED_TYPE and event.payload.get("outcome") == outcome:
            ctx.bind(game_id=event.bindings["game_id"])
            return True
        return False

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file, sorted."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
