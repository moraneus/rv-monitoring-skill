"""Scripted demo - no browser required.

Plays a handful of boards through the REAL game engine and injects the two
corrupted-event cheats the monitor must catch (a reveal after the boom, a
double reveal of the same cell), plus an over-flag. Every event is recorded
to a trace; then the same trace is replayed through a fresh engine - the
"replay gate" - which prints the verdicts and, for each violation, the
authored policy replayed with the failing step marked and the deciding
events attached.

    python demo.py                 # headless: play, record, replay, report
    python demo.py --dashboard     # also open the live dashboard and pause
    python demo.py --dashboard --port 7103

Exit code is non-zero if the replay gate does not see exactly the expected
violations, so this doubles as a self-check.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.replay import (                   # noqa: E402
    ReplaySource, TraceRecorder,
)
from behave_rv.verdict.explain import explain_verdict           # noqa: E402

from app.minesweeper import (                                   # noqa: E402
    Minesweeper, MonotonicClock, CELL_REVEAL, FLAG_PLACED, SOURCE,
)
from steps import build_registry, load_policies                # noqa: E402

TRACE = ROOT / "monitoring" / "traces" / "demo_session.jsonl"
MINES = [(0, c) for c in range(5)] + [(1, c) for c in range(5)]
EXPECTED_VIOLATIONS = 4


def banner(msg: str) -> None:
    print(f"\n=== {msg} ===")


def play(dashboard: bool, port: int) -> None:
    TRACE.parent.mkdir(exist_ok=True)
    TRACE.unlink(missing_ok=True)   # TraceRecorder appends; start each run fresh
    clock = MonotonicClock()
    registry = build_registry()
    policies = load_policies(registry)
    recorder = TraceRecorder(str(TRACE), clock=clock)

    dash = None
    if dashboard:
        dash = Dashboard(policies, registry=registry,
                         catalog=str(ROOT / "monitoring" / "catalog.json"),
                         app=[str(ROOT / "app" / "minesweeper.py")])
        url = dash.start(port=port)
        engine = Engine(policies, terminal_event_types=set(), grace=0.5,
                        quiescence_ttl=3600.0)
        from behave_rv.events.sources.subscription import QueueSource
        source = QueueSource()
        import threading
        threading.Thread(target=engine.run,
                         kwargs={"source": source, "sink": dash.sink},
                         daemon=True).start()
        print(f"live monitor: {url}  (watch the policy cards as boards play)")

    def emit(event: Event) -> None:
        event = recorder(event)
        if dash is not None:
            event = dash.tap(event)
            source.push(event)
        _RECORDED.append(event)

    pause = (lambda s=0.9: time.sleep(s)) if dashboard else (lambda s=0.0: None)

    banner("Board 1 - a clean game (no violation expected)")
    g1 = Minesweeper("demo-1-clean", emit, clock, mine_positions=MINES)
    g1.reveal(7, 7)          # floods a large safe region
    g1.flag(0, 0); g1.flag(0, 1); g1.flag(1, 0)   # three honest flags
    print("revealed a safe region, planted 3 flags - all policies holding")
    pause()

    banner("Board 2 - CHEAT: reveal after the boom (rule 1)")
    g2 = Minesweeper("demo-2-after-boom", emit, clock, mine_positions=MINES)
    g2.reveal(0, 0)          # steps on a mine -> boom, game over
    print("stepped on a mine at 0,0 -> boom (legal; game is over)")
    pause()
    emit(Event(CELL_REVEAL, clock(), {"game_id": "demo-2-after-boom", "cell": "6,6"},
               {"row": 6, "col": 6, "mine": False}, SOURCE))
    print("injected a raw cell.reveal at 6,6 AFTER the boom -> rule 1 violates")
    pause()

    banner("Board 3 - CHEAT: double-reveal the same cell (rule 2)")
    g3 = Minesweeper("demo-3-double", emit, clock, mine_positions=MINES)
    g3.reveal(7, 7)          # legitimate first reveal (incl 7,7)
    print("revealed 7,7 once (legitimately)")
    pause()
    emit(Event(CELL_REVEAL, clock(), {"game_id": "demo-3-double", "cell": "7,7"},
               {"row": 7, "col": 7, "mine": False}, SOURCE))
    print("injected a second raw cell.reveal at 7,7 -> rule 2 violates")
    pause()

    banner("Board 4 - CHEAT: plant an 11th flag on a 10-mine board (rule 3)")
    Minesweeper("demo-4-overflag", emit, clock, mine_positions=MINES)
    emit(Event(FLAG_PLACED, clock(), {"game_id": "demo-4-overflag"},
               {"flags": 11, "mines": 10, "cell": "3,3"}, SOURCE))
    print("injected flag.placed with flags=11, mines=10 -> rule 3 violates")
    pause()

    banner("Board 5 - CHEAT: a reveal with no game start (rule 4)")
    # No Minesweeper is constructed, so no game.started ever fires for this id.
    emit(Event(CELL_REVEAL, clock(), {"game_id": "demo-5-no-start", "cell": "2,2"},
               {"row": 2, "col": 2, "mine": False}, SOURCE))
    print("injected a raw cell.reveal under a game_id that never started "
          "-> rule 4 violates")
    pause()

    recorder.close()
    if dash is not None:
        print("\nDashboard is live. Press Ctrl-C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        dash.stop()


_RECORDED: list[Event] = []


def replay_gate() -> int:
    banner("Replay gate - re-running the recorded trace through a fresh engine")
    registry = build_registry()
    policies = load_policies(registry)
    by_id = {p.policy_id: p for p in policies}
    engine = Engine(policies, terminal_event_types=set())
    verdicts = engine.run(ReplaySource(str(TRACE)), emit_pending=True)

    violations = [v for v in verdicts if v.verdict == "violated"]
    for v in violations:
        policy = by_id[v.policy_id]
        print()
        print(explain_verdict(v, policy.authored_scenario, policy.failing_step_index))

    print(f"\nreplay gate: {len(verdicts)} verdicts, {len(violations)} violation(s) "
          f"(expected {EXPECTED_VIOLATIONS})")
    ok = len(violations) == EXPECTED_VIOLATIONS
    print("GATE PASS" if ok else "GATE FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Scripted Minesweeper RV demo")
    ap.add_argument("--dashboard", action="store_true",
                    help="start the live dashboard and pause on it")
    ap.add_argument("--port", type=int, default=7103)
    args = ap.parse_args()

    play(args.dashboard, args.port)
    if args.dashboard:
        return 0
    return replay_gate()


if __name__ == "__main__":
    raise SystemExit(main())
