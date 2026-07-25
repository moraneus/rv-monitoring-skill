"""The scripted traffic: a handful of Snake games, some healthy and some with
rule-breaking corruptions injected as raw stream events.

ONE source of truth, driven two ways:

* ``replay_check.py`` runs it with a fake clock (``advance`` ticks the clock,
  no real waiting) through ``InProcessSource`` for the deterministic gate.
* ``demo.py`` runs it with a service-relative real clock (``advance`` sleeps)
  through the live dashboard, so the user watches verdicts appear.

Healthy games drive the real ``SnakeGame`` engine. A "corruption" is, by
definition, an event that bypasses the engine's rules - so it is emitted as a
raw ``Event`` with a ``corrupted`` provenance, exactly the shape a real bug or
a tampered stream would produce.
"""

from __future__ import annotations

import random
from typing import Callable

from behave_rv.events.event import Event

from app.game import EVT_FOOD, EVT_GROW, EVT_MOVE, SnakeGame


def play(emit: Callable[[Event], None],
         clock: Callable[[], float],
         advance: Callable[[float], None]) -> list[tuple[str, str, str]]:
    """Drive every game. Returns (game_id, what happened, rule exercised)."""

    def raw(type: str, gid: str, payload: dict) -> None:
        """Inject a corrupted stream event (bypasses the engine's rules)."""
        advance(0.15)
        emit(Event(type, clock(), {"game_id": gid}, payload, "corrupted"))

    notes: list[tuple[str, str, str]] = []

    # --- Healthy 1: eats one food, grows, then dies at the east wall --------
    g = SnakeGame("g-clean", emit, clock, rng=random.Random(7))
    g.start(); advance(0.15)
    g.food = (13, g.snake[0][1])            # plant food three cells ahead
    for _ in range(12):                     # run right into the wall
        g.tick(); advance(0.15)
    notes.append(("g-clean", "healthy: scores 1 point, grows, dies at wall", "none"))

    # --- Healthy 2: a legal 90-degree turn, then dies at the south wall -----
    g2 = SnakeGame("g-turn", emit, clock, rng=random.Random(8))
    g2.start(); advance(0.15)
    g2.tick(); advance(0.15)                # move right
    g2.set_direction("down")               # right -> down is NOT a reversal
    for _ in range(12):                     # run down into the wall
        g2.tick(); advance(0.15)
    notes.append(("g-turn", "healthy: a legal 90-degree turn is accepted", "none"))

    # --- Fault A: a move arrives after the game is over ---------------------
    ga = SnakeGame("g-move-after-over", emit, clock, rng=random.Random(2))
    ga.start(); advance(0.15)
    for _ in range(12):
        ga.tick(); advance(0.15)            # dies at the wall -> "over"
    raw(EVT_MOVE, "g-move-after-over",
        {"direction": "right", "prev_direction": "right"})
    notes.append(("g-move-after-over",
                  "corrupt: a move is played after game over",
                  "rule 1 - no moves after over"))

    # --- Fault B: a point is scored after the game is over ------------------
    gb = SnakeGame("g-point-after-over", emit, clock, rng=random.Random(3))
    gb.start(); advance(0.15)
    for _ in range(12):
        gb.tick(); advance(0.15)            # dies at the wall -> "over"
    raw(EVT_FOOD, "g-point-after-over", {"score": 99})   # a point after over
    raw(EVT_GROW, "g-point-after-over", {"length": 5})   # growth follows in time,
    notes.append(("g-point-after-over",                  # so ONLY rule 1 fires
                  "corrupt: a point is scored after game over",
                  "rule 1 - no points after over"))

    # --- Fault C: food eaten but the snake never grows ---------------------
    gc = SnakeGame("g-food-no-grow", emit, clock, rng=random.Random(4))
    gc.start(); advance(0.15)
    gc.tick(); advance(0.15)                # one honest move, game still alive
    raw(EVT_FOOD, "g-food-no-grow", {"score": 1})        # point, but no growth
    advance(2.5)                            # let the 2-second deadline mature
    notes.append(("g-food-no-grow",
                  "corrupt: food eaten, snake never grows within 2s",
                  "rule 2 - food then growth in time"))

    # --- Fault D: a 180-degree reversal is accepted ------------------------
    gd = SnakeGame("g-reversal", emit, clock, rng=random.Random(5))
    gd.start(); advance(0.15)
    gd.tick(); advance(0.15)                # moving right
    raw(EVT_MOVE, "g-reversal",
        {"direction": "left", "prev_direction": "right"})   # straight reversal
    notes.append(("g-reversal",
                  "corrupt: a 180-degree reversal is accepted",
                  "rule 3 - no straight reversal"))

    advance(0.5)                            # let the last timers settle
    return notes
