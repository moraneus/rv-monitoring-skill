"""The monitorable vocabulary for the tic-tac-toe game.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

The application emits two event types, both keyed by ``game_id``:

* ``game.status``  - the tracked lifecycle states, one ``status`` field:
      "started" | "move" | "won" | "drawn"
  Move events additionally carry ``player`` (X|O), ``cell`` (0-8),
  ``prev_player`` (the mover of the immediately preceding move, or "none"),
  ``after_finish`` ("yes" if the move landed on an already-decided board,
  else "no"), and ``move_number``.
* ``game.over``    - the SEPARATE terminal event, ``outcome`` field:
      "won" | "drawn" | "abandoned".  It settles every open policy on the
  game and frees its monitor state.

Why a separate terminal type: an eventuality ("every game finishes") can
only be *violated* when a terminal ends the entity's life without the
awaited event. If "won"/"drawn" were themselves the terminal, an abandoned
game would leave no instance for the terminal to settle. ``game.over``
carrying ``abandoned`` is the honest lifecycle end that makes abandonment
observable.
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"

STATUS = "game.status"
OVER = "game.over"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    @registry.trigger('a game starts', step_id="game.lifecycle.started",
                      event_type=STATUS, correlation_key="game_id")
    def game_starts(ctx, event):
        return event.type == STATUS and event.payload.get("status") == "started"

    @registry.trigger('a move is played', step_id="game.move.any",
                      event_type=STATUS, correlation_key="game_id")
    def move_any(ctx, event):
        return event.type == STATUS and event.payload.get("status") == "move"

    @registry.trigger('a move is played by "{player}"', step_id="game.move.by",
                      event_type=STATUS, correlation_key="game_id")
    def move_by(ctx, event, player):
        return (event.type == STATUS and event.payload.get("status") == "move"
                and event.payload.get("player") == player)

    @registry.trigger('the opening move is played by "{player}"',
                      step_id="game.move.opening_by",
                      event_type=STATUS, correlation_key="game_id")
    def opening_move_by(ctx, event, player):
        return (event.type == STATUS and event.payload.get("status") == "move"
                and event.payload.get("move_number") == "1"
                and event.payload.get("player") == player)

    # LAW 1 predicate: strict alternation. The application stamps prev_player
    # from the TRUE move order at the emit site, so an honest move never has
    # player == prev_player; two moves in a row by the same mark do. This is a
    # per-move check, so it must be a self-contained predicate over a stamped
    # field, not a triggered form (which would arm once and settle).
    @registry.trigger('the same player moves twice in a row',
                      step_id="game.move.repeat",
                      event_type=STATUS, correlation_key="game_id")
    def move_repeat(ctx, event):
        return (event.type == STATUS and event.payload.get("status") == "move"
                and event.payload.get("player") == event.payload.get("prev_player"))

    # LAW 2 predicate: no move after the board is decided. The move carries
    # after_finish, stamped "yes" only when the board was already won/drawn
    # when the move was emitted. Self-contained (not scoped-never) on purpose:
    # game.over is a terminal, and a scoped never would settle satisfied at
    # the terminal, leaving a post-decision move on a fresh instance
    # unguarded (a false-green). A self-contained never on the stamped field
    # violates immediately even on a post-terminal instance.
    @registry.trigger('a move is played after the game is decided',
                      step_id="game.move.after_decided",
                      event_type=STATUS, correlation_key="game_id")
    def move_after_decided(ctx, event):
        return (event.type == STATUS and event.payload.get("status") == "move"
                and event.payload.get("after_finish") == "yes")

    # LAW 3 predicate: the game reached a decided state. has-happened over
    # this, with game.over as the terminal, satisfies on won/drawn and
    # violates when a game is abandoned before it is decided.
    @registry.trigger('a game is decided', step_id="game.decided.any",
                      event_type=STATUS, correlation_key="game_id")
    def game_decided(ctx, event):
        return (event.type == STATUS
                and event.payload.get("status") in ("won", "drawn"))

    @registry.trigger('a game is "{status}"', step_id="game.status.is",
                      event_type=STATUS, correlation_key="game_id")
    def game_status_is(ctx, event, status):
        return event.type == STATUS and event.payload.get("status") == status

    @registry.trigger('a game is over', step_id="game.over.any",
                      event_type=OVER, correlation_key="game_id")
    def game_over(ctx, event):
        return event.type == OVER

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
