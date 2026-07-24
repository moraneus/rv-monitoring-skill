"""Deterministic verdict gate: scripted Snake traffic through the real service
and the real policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

``play_scenarios`` is the single source of scripted traffic, reused by
``demo.py`` at the project root. It drives real games through ``SnakeService``
(healthy flows) and injects *corrupted* events - the kind a buggy or tampered
build could emit - to exercise each policy's fault path:

* healthy games: every eaten food grows the snake at once (rule 2 satisfied);
  no post-over activity, no accepted reversal.
* ``reversal-bug``: a move with ``reversal_accepted="true"`` is injected -
  rule 3 must fire.
* ``zombie``: after the real ``game.over``, a move and a score are injected -
  rule 1's two scenarios must both fire.
* ``no-grow``: a food is injected with no following grow; the timeline runs
  past the 2s deadline - rule 2 must fire on the timer.
* ``orphan``: a move and a score are injected for a game that was never
  started - rule 4's two scenarios (``before``) must both fire. The healthy
  games start before they ever move or score, so they satisfy rule 4.

Modelling decision: ``game.over`` is NOT a terminal event (see the report and
demo.py). A terminal would settle rule 1 as satisfied the instant the game
ended and make the injected post-over activity invisible - a false green. So
the ``zombie`` faults arrive after the real ``game.over`` and are still caught,
which is exactly the property this gate must prove.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.game import (                                          # noqa: E402
    DIRECTIONS, FOOD_EVENT, MOVE_EVENT, SCORE_EVENT, SnakeService,
)
from steps import build_registry, load_policies                # noqa: E402

TERMINAL_TYPES: set[str] = set()      # game.over is deliberately NOT terminal
EXPECTED = {"verdicts": 28, "violations": 6}


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def _food_ahead(service: SnakeService, game_id: str) -> None:
    """Place the food directly in front of the snake so the next tick eats it."""
    state = service.games[game_id]
    dx, dy = DIRECTIONS[state.heading]
    hx, hy = state.snake[0]
    state.food = (hx + dx, hy + dy)


def _drive_to_wall(service: SnakeService, game_id: str, clock: FakeClock) -> None:
    """Move the head next to the right wall and step into it (a real game over)."""
    state = service.games[game_id]
    hy = state.snake[0][1]
    state.snake = [(23, hy), (22, hy), (21, hy)]
    state.heading = state.pending = "right"
    clock.tick()
    service.tick(game_id)     # steps off the board -> game.over(reason="wall")


def play_scenarios(service: SnakeService, emit, clock: FakeClock) -> None:
    """Drive every seeded flow deterministically through the real service,
    injecting corrupted events where a policy's fault path is exercised."""

    # --- fault: a food with no following growth (rule 2, fired by the timer) ---
    service.new_game("no-grow", seed=7)
    clock.tick()
    emit(Event(FOOD_EVENT, clock(), {"game_id": "no-grow"},
               {"score": 10}, "corrupted-build"))
    # (no snake.grow follows; the timeline below runs well past the 2s deadline)

    # --- healthy: eat twice, each growth immediate, then die at the wall -------
    service.new_game("healthy-1", seed=1)
    for _ in range(2):
        _food_ahead(service, "healthy-1")
        clock.tick()
        service.tick("healthy-1")
    _drive_to_wall(service, "healthy-1", clock)

    # --- fault: a 180-degree reversal accepted (rule 3) -----------------------
    service.new_game("reversal-bug", seed=2)
    _food_ahead(service, "reversal-bug")
    clock.tick()
    service.tick("reversal-bug")
    clock.tick()
    emit(Event(MOVE_EVENT, clock(), {"game_id": "reversal-bug"},
               {"direction": "left", "reversal_accepted": "true", "turn": "turn"},
               "corrupted-build"))

    # --- fault: activity after game over (rule 1, both scenarios) -------------
    service.new_game("zombie", seed=3)
    _food_ahead(service, "zombie")
    clock.tick()
    service.tick("zombie")
    _drive_to_wall(service, "zombie", clock)          # real game.over
    clock.tick(1.0)
    emit(Event(MOVE_EVENT, clock(), {"game_id": "zombie"},
               {"direction": "right", "reversal_accepted": "false", "turn": "straight"},
               "corrupted-build"))
    clock.tick()
    emit(Event(SCORE_EVENT, clock(), {"game_id": "zombie"},
               {"score": 999, "points": 989}, "corrupted-build"))
    # By now event time has passed the no-grow food's 2s deadline (t=1.0 -> 3.0),
    # so its timer has already fired violated - no extra clock-advance needed.

    # --- fault: activity for a game that was never started (rule 4) -----------
    clock.tick()
    emit(Event(MOVE_EVENT, clock(), {"game_id": "orphan"},
               {"direction": "up", "reversal_accepted": "false", "turn": "straight"},
               "corrupted-build"))
    clock.tick()
    emit(Event(SCORE_EVENT, clock(), {"game_id": "orphan"},
               {"score": 10, "points": 10}, "corrupted-build"))


def build_engine(policies):
    # grace=0: the scripted order is authoritative, no reordering window needed.
    return Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=0.0)


def main() -> int:
    source = InProcessSource()
    service = SnakeService(source.emit, clock=(clock := FakeClock()))
    play_scenarios(service, source.emit, clock)

    registry = build_registry()
    policies = load_policies(registry)
    verdicts = build_engine(policies).run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for verdict in verdicts:
        print(f"{verdict.verdict:9}  {verdict.entity_key}  {verdict.policy_id}")
    for verdict in violations:
        policy = by_id[verdict.policy_id]
        print()
        print(explain_verdict(verdict, policy.authored_scenario,
                              policy.failing_step_index))

    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s)")
    if EXPECTED["verdicts"] is None:
        print("EXPECTED not pinned yet: review the output above, then set "
              "EXPECTED to lock this behaviour in.")
        return 1
    ok = (len(verdicts) == EXPECTED["verdicts"]
          and len(violations) == EXPECTED["violations"])
    if not ok:
        print(f"MISMATCH: expected {EXPECTED}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
