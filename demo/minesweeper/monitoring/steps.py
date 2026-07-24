"""The monitorable vocabulary for Minesweeper.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity; policies bind to it across renames.
  Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean. No side effects.
* When rewording a phrasing, keep the old wording as an alias.

Two correlation keys are in play, and they are what keep the policies in the
single-entity fragment:
* ``game_id``            - the whole game (rule 1 "no reveal after boom",
                           rule 3 "flags never exceed mines").
* ``(game_id, cell)``    - one specific cell of one game (rule 2 "no cell is
                           ever revealed twice").

``cell.reveal`` (the reveal ACTION) is observed under BOTH keys by two
separate steps - a game-wide reveal and a same-cell reveal - so each policy
stays on exactly one key.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # --- lifecycle: the game has started (key: game_id) -----------------
    # Observes game.started, already emitted at board construction. Used by
    # the "a cell is only revealed after the game has started" policy.
    @registry.trigger('the game has started',
                      step_id="game.lifecycle.started",
                      event_type="game.started",
                      correlation_key="game_id")
    def game_has_started(ctx, event):
        return event.type == "game.started"

    # --- rule 1: no reveal after a mine explodes (key: game_id) ---------
    @registry.trigger('a mine explodes',
                      step_id="game.mine.exploded",
                      event_type="mine.exploded",
                      correlation_key="game_id")
    def mine_explodes(ctx, event):
        return event.type == "mine.exploded"

    @registry.trigger('a cell is revealed',
                      step_id="game.cell.reveal",
                      event_type="cell.reveal",
                      correlation_key="game_id")
    def cell_revealed_in_game(ctx, event):
        return event.type == "cell.reveal"

    # --- rule 2: no cell is ever revealed twice (key: game_id, cell) ----
    # Scope opens on the cell's revealed STATE, which the game emits strictly
    # after the reveal action; the forbidden event is any later reveal ACTION
    # on that same cell.
    @registry.trigger('the same cell has been revealed',
                      step_id="cell.state.revealed",
                      event_type="cell.revealed",
                      correlation_key=("game_id", "cell"))
    def same_cell_state_revealed(ctx, event):
        return event.type == "cell.revealed"

    @registry.trigger('the same cell is revealed again',
                      step_id="cell.reveal.repeat",
                      event_type="cell.reveal",
                      correlation_key=("game_id", "cell"))
    def same_cell_reveal_again(ctx, event):
        return event.type == "cell.reveal"

    # --- rule 3: flags never exceed the mine count (key: game_id) -------
    # The game stamps the running flag count and the board's mine count into
    # every flag.placed event, so this is a PURE predicate over one event's
    # payload - not cross-event counting (which is out of fragment).
    @registry.trigger('more flags are planted than there are mines',
                      step_id="game.flags.exceed_mines",
                      event_type="flag.placed",
                      correlation_key="game_id")
    def flags_exceed_mines(ctx, event):
        return (event.type == "flag.placed"
                and int(event.payload.get("flags", 0))
                > int(event.payload.get("mines", 0)))

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
