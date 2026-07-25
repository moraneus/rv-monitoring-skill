"""The monitorable vocabulary for the Memory-pairs game.

Conventions (see the rv skill's project-files reference):
* ``build_registry()`` is a side-effect-free factory; the behave-rv CLI
  detects and uses it.
* ``step_id`` is permanent identity (``<domain>.<event>.<what>``); policies
  bind to it across renames. Never reuse one for a different meaning.
* Predicates are pure: read the event, return a boolean.
* When rewording a phrasing, keep the old wording as an alias.

Two correlation keys are in play, both single-entity (one card game per key):
  * ``game_id``                      - the whole game (rules 1 and 3).
  * ``(game_id, attempt_id)``        - one flip attempt (rule 2's deadline).
The second is occurrence keying: a `within` deadline arms once per entity, so
each attempt is its own entity to have every attempt's 3-second clock checked
rather than only the first (see references/operators.md).
"""

from pathlib import Path

from behave_rv.catalog.registry import StepRegistry
from behave_rv.compile.compiler import compile_feature

POLICY_DIR = Path(__file__).parent / "policies"


def build_registry() -> StepRegistry:
    registry = StepRegistry()

    # -- rule 1: a card already part of a found pair is flipped again -------
    # History-stamped predicate: the emit site knows, at flip time, whether
    # the card was already matched. A self-contained `never` over this field
    # checks EVERY flip and never settles early.
    @registry.trigger('a matched card is flipped again',
                      step_id="card.flipped.rematch",
                      event_type="card.flipped", correlation_key="game_id")
    def matched_card_reflipped(ctx, event):
        return (event.type == "card.flipped"
                and event.payload.get("already_matched") is True)

    # -- rule 2: the second card of an attempt / its resolution ------------
    @registry.trigger("the second card of an attempt is flipped",
                      step_id="card.flipped.second",
                      event_type="card.flipped",
                      correlation_key=("game_id", "attempt_id"))
    def second_card_flipped(ctx, event):
        return (event.type == "card.flipped"
                and event.payload.get("slot") == "second")

    @registry.trigger("the attempt resolves",
                      step_id="attempt.resolved.any",
                      event_type="attempt.resolved",
                      correlation_key=("game_id", "attempt_id"))
    def attempt_resolves(ctx, event):
        return event.type == "attempt.resolved"

    @registry.trigger('the attempt resolves as "{outcome}"',
                      step_id="attempt.resolved.outcome",
                      event_type="attempt.resolved",
                      correlation_key=("game_id", "attempt_id"))
    def attempt_resolves_as(ctx, event, outcome):
        return (event.type == "attempt.resolved"
                and event.payload.get("outcome") == outcome)

    # -- rule 3: anything happens after the game is complete ---------------
    # History-stamped: every emission carries whether the game had already
    # ended. Self-contained `never`; and because game.completed is the
    # terminal event, any post-completion flip spawns a fresh instance that
    # still violates immediately (no terminal-window false-green).
    @registry.trigger("a card is flipped after the game is over",
                      step_id="card.flipped.postgame",
                      event_type="card.flipped", correlation_key="game_id")
    def card_flipped_after_over(ctx, event):
        return (event.type == "card.flipped"
                and event.payload.get("after_completion") is True)

    # -- general vocabulary (over-exposed; enriches authoring) -------------
    @registry.trigger("a card is flipped",
                      step_id="card.flipped.any",
                      event_type="card.flipped", correlation_key="game_id")
    def any_card_flipped(ctx, event):
        return event.type == "card.flipped"

    @registry.trigger("the game is completed",
                      step_id="game.completed.any",
                      event_type="game.completed", correlation_key="game_id")
    def game_completed(ctx, event):
        return event.type == "game.completed"

    return registry


def load_policies(registry: StepRegistry):
    """Compile every .feature under policies/, one Feature per file."""
    policies = []
    for path in sorted(POLICY_DIR.glob("*.feature")):
        policies.extend(compile_feature(path.read_text(), registry))
    return policies
