"""The Snake game engine - pure logic, instrumented for runtime verification.

The engine is UI-agnostic: the browser server (``server.py``) and the scripted
demo (``demo.py``) both drive the same ``SnakeService``. Following the rv
instrumentation conventions:

* ``emit`` and ``clock`` are injected, so the same service runs live (real
  clock, events into the monitor queue) and under the deterministic replay gate
  (fake clock, events into a list) with identical code paths.
* Every state transition constructs an ``Event(...)`` directly at the site,
  with module-level string constants for the event types and dict literals for
  bindings and payloads - that is the surface the stability analysis anchors on.
* Predicates never live here; the engine only *emits*. Verdicts belong to the
  deterministic monitor.

Correctness invariants the engine enforces (and the monitor independently
verifies): a 180-degree turn is rejected at input, every eaten food grows the
snake in the same tick, and a dead game stops ticking. The demo shows the
monitor catching these same properties when *corrupted* events - the kind a
buggy or tampered build could emit - are injected into the stream.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Optional

from behave_rv.events.event import Event

# --- Event types: stable identities the catalog and policies bind to. ---------
STATUS_EVENT = "game.status"     # game lifecycle: started / over
MOVE_EVENT = "snake.move"        # one accepted step of the snake
FOOD_EVENT = "snake.food"        # the snake's head reached food
GROW_EVENT = "snake.grow"        # the snake's body grew by one
SCORE_EVENT = "game.score"       # points were added
SOURCE = "snake-engine"

# --- Board and rules ----------------------------------------------------------
GRID_W = 24
GRID_H = 24
START_LENGTH = 3
POINTS_PER_FOOD = 10
TICK_EPSILON = 1e-3              # keeps ordered emissions on distinct timestamps

DIRECTIONS: dict[str, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


def _is_opposite(a: str, b: str) -> bool:
    (ax, ay), (bx, by) = DIRECTIONS[a], DIRECTIONS[b]
    return ax == -bx and ay == -by


class GameState:
    """The board state for a single game (one monitored entity)."""

    def __init__(self, game_id: str, seed: Optional[int] = None):
        self.game_id = game_id
        self.rng = random.Random(seed)
        cx, cy = GRID_W // 2, GRID_H // 2
        # head first; the snake starts heading right, in the middle of the board.
        self.snake: list[tuple[int, int]] = [(cx - i, cy) for i in range(START_LENGTH)]
        self.heading = "right"
        self.pending = "right"
        self.score = 0
        self.alive = True
        self.reason = ""
        self.food = self._spawn_food()

    def _spawn_food(self) -> tuple[int, int]:
        empty = [(x, y) for x in range(GRID_W) for y in range(GRID_H)
                 if (x, y) not in self.snake]
        return self.rng.choice(empty) if empty else self.snake[0]

    def snapshot(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "grid_w": GRID_W,
            "grid_h": GRID_H,
            "snake": [list(cell) for cell in self.snake],
            "food": list(self.food),
            "score": self.score,
            "alive": self.alive,
            "reason": self.reason,
            "heading": self.heading,
            "length": len(self.snake),
        }


class SnakeService:
    """Drives games and emits their observable behaviour to the monitor.

    ``emit`` receives an :class:`Event`; ``clock`` returns event-time seconds.
    """

    def __init__(self, emit: Callable[[Event], Any], clock: Callable[[], float] = time.time):
        self._emit = emit
        self._clock = clock
        self._last_t = -1.0
        self.games: dict[str, GameState] = {}

    def _now(self) -> float:
        """A strictly increasing event time, so ordered emissions never tie."""
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + TICK_EPSILON
        self._last_t = t
        return t

    # --- lifecycle ------------------------------------------------------------
    def new_game(self, game_id: str, seed: Optional[int] = None) -> GameState:
        state = GameState(game_id, seed=seed)
        self.games[game_id] = state
        self._emit(Event(STATUS_EVENT, self._now(), {"game_id": game_id},
                         {"status": "started", "grid_w": GRID_W, "grid_h": GRID_H},
                         SOURCE))
        return state

    def set_direction(self, game_id: str, direction: str) -> str:
        """Queue a direction change. A 180-degree reversal is rejected here -
        the engine never turns the snake straight back into itself."""
        state = self.games.get(game_id)
        if state is None or not state.alive or direction not in DIRECTIONS:
            return "ignored"
        if _is_opposite(direction, state.heading):
            return "rejected"          # the rule-3 invariant, enforced at input
        state.pending = direction
        return "accepted"

    def tick(self, game_id: str) -> Optional[GameState]:
        """Advance the game by one step, emitting what changed."""
        state = self.games.get(game_id)
        if state is None or not state.alive:
            return state

        new_heading = state.pending
        reversal_accepted = "true" if _is_opposite(new_heading, state.heading) else "false"
        turn = "straight" if new_heading == state.heading else "turn"
        state.heading = new_heading

        dx, dy = DIRECTIONS[new_heading]
        head_x, head_y = state.snake[0]
        nxt = (head_x + dx, head_y + dy)

        if not (0 <= nxt[0] < GRID_W and 0 <= nxt[1] < GRID_H):
            return self._end_game(state, "wall")

        will_eat = nxt == state.food
        body = state.snake if will_eat else state.snake[:-1]
        if nxt in body:
            return self._end_game(state, "self")

        state.snake.insert(0, nxt)
        self._emit(Event(MOVE_EVENT, self._now(), {"game_id": game_id},
                         {"direction": new_heading, "reversal_accepted": reversal_accepted,
                          "turn": turn}, SOURCE))

        if will_eat:
            state.score += POINTS_PER_FOOD
            self._emit(Event(FOOD_EVENT, self._now(), {"game_id": game_id},
                             {"score": state.score}, SOURCE))
            self._emit(Event(GROW_EVENT, self._now(), {"game_id": game_id},
                             {"length": len(state.snake)}, SOURCE))
            self._emit(Event(SCORE_EVENT, self._now(), {"game_id": game_id},
                             {"score": state.score, "points": POINTS_PER_FOOD}, SOURCE))
            state.food = state._spawn_food()
        else:
            state.snake.pop()
        return state

    def _end_game(self, state: GameState, reason: str) -> GameState:
        state.alive = False
        state.reason = reason
        self._emit(Event(STATUS_EVENT, self._now(), {"game_id": state.game_id},
                         {"status": "over", "reason": reason, "score": state.score},
                         SOURCE))
        return state

    def snapshot(self, game_id: str) -> Optional[dict[str, Any]]:
        state = self.games.get(game_id)
        return state.snapshot() if state else None
