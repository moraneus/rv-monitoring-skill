"""Scripted demo mode - no browser needed.

Plays a few boards through the REAL game engine and the committed policies,
then injects CORRUPTED events (a stream that bypassed the board's own guards)
to show the monitor catching each violation with the authored scenario
replayed and the failing step marked:

    python demo.py

Healthy boards produce zero violations; each cheat produces exactly one, keyed
to the entity it happened on. This is the same wiring the replay gate uses -
the gate asserts the counts, this narrates them.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from steps import build_registry, load_policies                 # noqa: E402
from app.game import (                                          # noqa: E402
    MinesweeperGame, BOARD_REVEAL, CELL_REVEAL, FLAG_SET, SOURCE,
)

TERMINAL_TYPES = {"game.done"}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1e-3
        return self.now

    def tick(self, dt=1.0):
        self.now += dt


def banner(text):
    print("\n" + "=" * 68)
    print(text)
    print("=" * 68)


def board_healthy(emit, clock):
    banner("BOARD 1  healthy play - reveal, flag real mines, clear the board")
    g = MinesweeperGame("board-1", emit, clock, rng=random.Random(7))
    g.reveal(0, 0)
    for cell in sorted(g.mine_at)[:3]:
        g.toggle_flag(*cell)
    for r in range(g.rows):
        for c in range(g.cols):
            if (r, c) not in g.mine_at:
                g.reveal(r, c)
    print(f"  outcome: {g.status}  (revealed {len(g.revealed)}/54 safe squares, "
          f"{len(g.flagged)} flags <= {g.mines} mines) -> no violation expected")


def board_lost_clean(emit, clock):
    banner("BOARD 2  honest loss - step on a mine, board freezes, no further moves")
    g = MinesweeperGame("board-2", emit, clock, rng=random.Random(3))
    g.reveal(0, 0)
    mine = sorted(g.mine_at)[0]
    g.reveal(*mine)
    print(f"  boom at {mine}. The engine's guard freezes the board; a real player "
          f"can do nothing more -> no violation (the monitor only fires on a\n"
          f"  reveal that arrives ANYWAY, which the next board injects).")


def cheat_reveal_after_boom(emit, clock):
    banner("CHEAT A  corrupted stream: a reveal after the mine exploded")
    g = MinesweeperGame("board-3", emit, clock, rng=random.Random(1))
    g.reveal(0, 0)
    mine = sorted(g.mine_at)[0]
    g.reveal(*mine)                     # legit boom
    clock.tick()
    emit(Event(BOARD_REVEAL, clock(), {"game_id": "board-3"},
               {"cell": "5,5", "row": 5, "col": 5, "mine": False}, SOURCE))
    print("  injected board.reveal for cell 5,5 AFTER board-3 detonated.")


def cheat_double_reveal(emit, clock):
    banner("CHEAT B  corrupted stream: the same square revealed twice")
    g = MinesweeperGame("board-4", emit, clock, rng=random.Random(2))
    g.reveal(0, 0)
    target = sorted(g.revealed)[0]
    clock.tick()
    emit(Event(CELL_REVEAL, clock(),
               {"game_id": "board-4", "cell": f"{target[0]},{target[1]}"},
               {"row": target[0], "col": target[1], "mine": False}, SOURCE))
    print(f"  injected a second cell.reveal for square {target[0]},{target[1]}.")


def cheat_flag_overflow(emit, clock):
    banner("CHEAT C  corrupted stream: more flags planted than there are mines")
    clock.tick()
    emit(Event(FLAG_SET, clock(), {"game_id": "board-5"},
               {"flags": 11, "mines": 10}, SOURCE))
    print("  injected flag.set with flags=11 over a 10-mine budget.")


def main() -> int:
    source = InProcessSource()
    clock = Clock()
    for flow in (board_healthy, board_lost_clean,
                 cheat_reveal_after_boom, cheat_double_reveal, cheat_flag_overflow):
        flow(source.emit, clock)
        clock.tick(5)

    registry = build_registry()
    policies = load_policies(registry)
    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES)
    verdicts = engine.run(source, emit_pending=True)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    banner(f"VERDICTS  {len(violations)} violation(s) across {len(verdicts)} verdict(s)")
    for v in violations:
        policy = by_id[v.policy_id]
        print()
        print(explain_verdict(v, policy.authored_scenario, policy.failing_step_index))

    print(f"\nsummary: {len(violations)} violation(s) - "
          "one per injected cheat, healthy boards clean.")
    return 0 if len(violations) == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
