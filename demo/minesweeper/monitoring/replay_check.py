"""Deterministic verdict gate: scripted traffic through the real game and the
real policies, exit-coded for CI.

    python monitoring/replay_check.py     # exit 1 on unexpected verdicts

The healthy flows (a safe game; a legitimate mine hit that ends the game) go
through the real ``Minesweeper`` service and MUST produce zero violations.
The three faults are corrupted events injected directly onto the stream -
exactly what a compromised or bypassed component would emit - so the monitor,
which trusts only the event stream, catches each one:

* reveal after the boom          -> rule 1 (01_no_reveal_after_boom)
* the same cell revealed twice    -> rule 2 (02_no_double_reveal)
* an 11th flag on a 10-mine board -> rule 3 (03_flags_never_exceed_mines)

There is no terminal event (game.over is informational, not terminal), so the
prohibitions stay armed after the boom and the terminal-windows concern does
not apply: the post-boom reveal is caught even though it arrives after
game.over. Update EXPECTED only for intended behaviour changes, and say so.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from behave_rv.engine.loop import Engine                       # noqa: E402
from behave_rv.events.event import Event                       # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.minesweeper import (                                   # noqa: E402
    Minesweeper, DeterministicClock, CELL_REVEAL, FLAG_PLACED, SOURCE,
)
from steps import build_registry, load_policies                # noqa: E402

# game.over is deliberately NOT terminal (see module docstring).
TERMINAL_TYPES: set[str] = set()
EXPECTED = {"verdicts": 124, "violations": 4}

# Ten mines packed into the top two rows, leaving the rest of the board safe.
MINES = [(0, c) for c in range(5)] + [(1, c) for c in range(5)]


def simulate_traffic(emit) -> None:
    clock = DeterministicClock()

    # --- healthy flow 1: a safe game, normal reveals and flags -----------
    safe = Minesweeper("g_safe", emit, clock, mine_positions=MINES)
    safe.reveal(7, 7)            # floods a large safe region
    safe.reveal(5, 6)            # already revealed by the flood -> no-op
    safe.flag(0, 0)              # flag three suspected mines (<= 10)
    safe.flag(0, 1)
    safe.flag(1, 0)

    # --- healthy flow 2: a legitimate mine hit ends the game (no cheat) ---
    boom_ok = Minesweeper("g_boom_ok", emit, clock, mine_positions=MINES)
    boom_ok.reveal(0, 0)         # steps on a mine -> boom, game over
    boom_ok.reveal(6, 6)         # honest game no-ops after game over

    # --- fault A: reveal after the boom (rule 1) -------------------------
    boom = Minesweeper("g_boom_cheat", emit, clock, mine_positions=MINES)
    boom.reveal(0, 0)            # boom
    emit(Event(CELL_REVEAL, clock(), {"game_id": "g_boom_cheat", "cell": "6,6"},
               {"row": 6, "col": 6, "mine": False}, SOURCE))   # injected reveal

    # --- fault B: the same cell revealed twice (rule 2) ------------------
    dbl = Minesweeper("g_double_cheat", emit, clock, mine_positions=MINES)
    dbl.reveal(7, 7)            # legitimate first reveal of a region incl (7,7)
    emit(Event(CELL_REVEAL, clock(), {"game_id": "g_double_cheat", "cell": "7,7"},
               {"row": 7, "col": 7, "mine": False}, SOURCE))   # injected repeat

    # --- fault C: an 11th flag on a 10-mine board (rule 3) ---------------
    flags = Minesweeper("g_flag_cheat", emit, clock, mine_positions=MINES)
    emit(Event(FLAG_PLACED, clock(), {"game_id": "g_flag_cheat"},
               {"flags": 11, "mines": 10, "cell": "3,3"}, SOURCE))  # injected

    # --- fault D: a reveal with no preceding game start (rule 4) ----------
    # No Minesweeper is constructed for this game_id, so no game.started event
    # is ever emitted; a raw cell.reveal arriving under it models a
    # correlation-key or ordering bug in the emitter.
    emit(Event(CELL_REVEAL, clock(), {"game_id": "g_no_start", "cell": "2,2"},
               {"row": 2, "col": 2, "mine": False}, SOURCE))        # injected


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
