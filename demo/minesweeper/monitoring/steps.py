"""The monitorable vocabulary for the Minesweeper board.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean. Nothing else.
* When rewording a phrasing, keep the old wording as an alias.

Two correlation keys are in play. Board-wide rules key on ``game_id``;
"revealed at most once" keys on the composite ``(game_id, cell)`` so every
square is its own monitored entity.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # -- board-wide vocabulary (key: game_id) -------------------------------

    @registry.trigger("a mine explodes", step_id="board.mine.boom",
                      event_type="mine.boom", correlation_key="game_id")
    def mine_explodes(ctx, event):
        return event.type == "mine.boom"

    @registry.trigger("a cell is revealed on the board", step_id="board.reveal.any",
                      event_type="board.reveal", correlation_key="game_id")
    def cell_revealed_on_board(ctx, event):
        return event.type == "board.reveal"

    @registry.trigger("the planted flags outnumber the mines",
                      step_id="board.flags.overflow",
                      event_type="flag.set", correlation_key="game_id")
    def flags_outnumber_mines(ctx, event):
        return (event.type == "flag.set"
                and event.payload.get("flags", 0) > event.payload.get("mines", 0))

    # -- per-square vocabulary (key: game_id + cell) ------------------------

    @registry.trigger("a cell is revealed", step_id="cell.reveal.occurs",
                      event_type="cell.reveal", correlation_key=("game_id", "cell"))
    def cell_reveal_occurs(ctx, event):
        return event.type == "cell.reveal"

    @registry.trigger("that cell was already revealed", step_id="cell.seen.state",
                      event_type="cell.seen", correlation_key=("game_id", "cell"))
    def cell_already_revealed(ctx, event):
        return event.type == "cell.seen"

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
