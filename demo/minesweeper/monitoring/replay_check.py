"""Deterministic verdict gate: scripted traffic through the real game engine
and the committed policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The healthy flow is a full, real game played to a win (zero violations - the
board engine's own guards keep play legal). The faulty flows are CORRUPTED
event streams injected straight onto the source, bypassing those guards, one
per rule:

* reveal-after-boom : a board reveal emitted after the mine detonated.
* double-reveal     : a second reveal of a square already seen.
* flag-overflow     : a flag count above the mine budget.

Update EXPECTED only for intended behaviour changes, and say so in the commit.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from steps import build_registry, load_policies                 # noqa: E402
from app.game import (                                          # noqa: E402
    MinesweeperGame, BOARD_REVEAL, CELL_REVEAL, FLAG_SET, SOURCE,
)

TERMINAL_TYPES = {"game.done"}     # a cleared board settles its game-keyed policies
EXPECTED = {"verdicts": 92, "violations": 3}


class FakeClock:
    """Strictly increasing event time: every emit gets a distinct timestamp so
    ordered emissions never collide. ``tick`` opens a wider gap between flows."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1e-3
        return self.now

    def tick(self, dt: float = 1.0):
        self.now += dt


def play_healthy_win(emit, clock) -> None:
    """A real board played to completion with no illegal move: reveal a safe
    opening square, plant a few flags within budget, then clear every non-mine
    square. The engine's guards make this clean by construction."""
    game = MinesweeperGame("game-healthy", emit, clock, rng=random.Random(7))
    game.reveal(0, 0)                       # first click places mines, always safe
    for cell in sorted(game.mine_at)[:3]:   # flag a few real mines, well under budget 10
        game.toggle_flag(*cell)
    for r in range(game.rows):
        for c in range(game.cols):
            if (r, c) not in game.mine_at:
                game.reveal(r, c)           # revealed squares are inert; only new ones fire
    assert game.status == "won", game.status


def cheat_reveal_after_boom(emit, clock) -> None:
    """Detonate a real board, then inject a reveal that arrives after the boom."""
    game = MinesweeperGame("game-boom", emit, clock, rng=random.Random(1))
    game.reveal(0, 0)                       # safe opener, places mines
    mine_r, mine_c = sorted(game.mine_at)[0]
    game.reveal(mine_r, mine_c)             # steps on a mine -> mine.boom, board frozen
    clock.tick()
    # corrupted stream: a board reveal after the detonation (bypasses the guard)
    emit(Event(BOARD_REVEAL, clock(), {"game_id": "game-boom"},
               {"cell": "3,3", "row": 3, "col": 3, "mine": False}, SOURCE))


def cheat_double_reveal(emit, clock) -> None:
    """Reveal a square legally, then inject a second reveal of that same square."""
    game = MinesweeperGame("game-dup", emit, clock, rng=random.Random(2))
    game.reveal(0, 0)
    # find a revealed non-mine square to duplicate
    target = sorted(game.revealed)[0]
    clock.tick()
    # corrupted stream: the same (game_id, cell) revealed a second time
    emit(Event(CELL_REVEAL, clock(),
               {"game_id": "game-dup", "cell": f"{target[0]},{target[1]}"},
               {"row": target[0], "col": target[1], "mine": False}, SOURCE))


def cheat_flag_overflow(emit, clock) -> None:
    """Inject a flag count above the mine budget."""
    clock.tick()
    emit(Event(FLAG_SET, clock(), {"game_id": "game-flags"},
               {"flags": 11, "mines": 10}, SOURCE))


def simulate_traffic(emit) -> None:
    clock = FakeClock()
    play_healthy_win(emit, clock);      clock.tick(5)
    cheat_reveal_after_boom(emit, clock); clock.tick(5)
    cheat_double_reveal(emit, clock);   clock.tick(5)
    cheat_flag_overflow(emit, clock)


def main() -> int:
    source = InProcessSource()
    simulate_traffic(source.emit)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    verdicts = engine.run(source, emit_pending=True)

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
