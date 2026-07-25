"""The Snake game engine - authoritative game logic that is born monitorable.

The engine owns all rules (movement, growth, collision, game-over) and emits a
normalized ``Event`` at every state transition. Instrumentation is additive:
the ``Event(...)`` constructions sit beside the game logic, they never reshape
it. ``emit`` and ``clock`` are injected so the SAME engine runs live (real
clock, events to the monitor) and under the scripted demo (fake clock, events
into a list) identically.

Stdlib only.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Optional

from behave_rv.events.event import Event

# --- Event types: module-level constants, referenced by name so the stability
# --- analyzer can resolve them (a computed type would degrade to <dynamic>).
EVT_STATUS = "game.status"   # lifecycle: status in {"started", "over"}
EVT_MOVE = "game.move"       # one accepted step; carries heading + previous heading
EVT_FOOD = "game.food"       # a point is scored (food eaten)
EVT_GROW = "game.grow"       # the snake grew by one segment
SOURCE = "snake-engine"

# The four headings and their exact opposites. A 180-degree reversal is a
# heading whose opposite equals the previous heading.
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
DELTA = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

DEFAULT_W = 20
DEFAULT_H = 20
START_LEN = 3


class SnakeGame:
    """One game session. Correlation key: ``game_id``."""

    def __init__(
        self,
        game_id: str,
        emit: Callable[[Event], None],
        clock: Callable[[], float],
        width: int = DEFAULT_W,
        height: int = DEFAULT_H,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._game_id = game_id
        self._emit_raw = emit
        self._clock = clock
        self._w = width
        self._h = height
        self._rng = rng or random.Random()
        self._last_t = 0.0

        # Snake occupies cells head-first; starts centred, heading right.
        cx, cy = width // 2, height // 2
        self.snake: list[tuple[int, int]] = [(cx - i, cy) for i in range(START_LEN)]
        self.direction = "right"        # current heading (last applied)
        self._pending = "right"         # next heading, validated at input time
        self.score = 0
        self.over = False
        self.reason = ""
        self.food = self._place_food()
        self._started = False

    # -- instrumentation helper -------------------------------------------
    def _emit(self, type: str, payload: dict[str, Any]) -> None:
        """Stamp a strictly-increasing event_time and push the event.

        Ordered emissions within one tick (move -> food -> grow, or move ->
        over) must not share a timestamp, or the engine would order them
        canonically by content. The +1e-3 nudge keeps them distinct while
        staying at wall rate for live streams.
        """
        t = self._clock()
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        self._emit_raw(
            Event(
                type=type,
                event_time=t,
                bindings={"game_id": self._game_id},
                payload=payload,
                source=SOURCE,
            )
        )

    def _place_food(self) -> tuple[int, int]:
        occupied = set(self.snake)
        free = [
            (x, y)
            for x in range(self._w)
            for y in range(self._h)
            if (x, y) not in occupied
        ]
        return self._rng.choice(free) if free else (0, 0)

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._emit(
            EVT_STATUS,
            {"status": "started", "score": self.score, "length": len(self.snake)},
        )

    def set_direction(self, direction: str) -> bool:
        """Queue an input heading. A 180-degree reversal of the current heading
        is REFUSED here and never becomes an accepted move (rule 3). Returns
        whether the input was accepted."""
        if direction not in DELTA:
            return False
        if self.over:
            return False
        if OPPOSITE[self.direction] == direction:
            return False   # a straight reversal into itself - refused
        self._pending = direction
        return True

    def tick(self) -> None:
        """Advance the snake one cell. Emits a move, then food+grow if a point
        is scored, or an over status on collision."""
        if self.over or not self._started:
            return

        prev_direction = self.direction
        self.direction = self._pending
        dx, dy = DELTA[self.direction]
        hx, hy = self.snake[0]
        nx, ny = hx + dx, hy + dy

        # A move is accepted: emit the step with its heading and the previous
        # heading, so a per-move 180-reversal is detectable from the stream.
        self._emit(EVT_MOVE, {"direction": self.direction,
                              "prev_direction": prev_direction})

        # Wall collision ends the game.
        if nx < 0 or nx >= self._w or ny < 0 or ny >= self._h:
            self._game_over("wall")
            return

        eats = (nx, ny) == self.food
        # Self collision: hitting the body ends the game. The tail cell is
        # vacated this tick unless we are growing.
        body = self.snake if eats else self.snake[:-1]
        if (nx, ny) in body:
            self._game_over("self")
            return

        self.snake.insert(0, (nx, ny))
        if eats:
            self.score += 1
            self._emit(EVT_FOOD, {"score": self.score})
            self._emit(EVT_GROW, {"length": len(self.snake)})
            self.food = self._place_food()
        if not eats:
            self.snake.pop()

    def _game_over(self, reason: str) -> None:
        self.over = True
        self.reason = reason
        self._emit(
            EVT_STATUS,
            {"status": "over", "reason": reason,
             "score": self.score, "length": len(self.snake)},
        )

    # -- view snapshot ----------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "game_id": self._game_id,
            "w": self._w,
            "h": self._h,
            "snake": [list(c) for c in self.snake],
            "food": list(self.food),
            "score": self.score,
            "length": len(self.snake),
            "direction": self.direction,
            "over": self.over,
            "reason": self.reason,
        }
