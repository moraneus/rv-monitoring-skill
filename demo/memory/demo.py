"""Scripted demo - no browser needed.

    python demo.py                 # live dashboard at :7105, plays the games,
                                   #   then holds so you can watch. Ctrl-C to stop.
    python demo.py --auto-exit 6   # run, snapshot, and exit (used by tests/CI)

It plays a healthy game and then the three cheats, injected as CORRUPTED
events straight into the live stream (the honest service never emits them):

  * G-cheat-rematch : a card already in a found pair is flipped again  -> rule 1
  * G-cheat-hang    : a second card is flipped and never resolved       -> rule 2
                       (the 3-second wall timer fires it, live)
  * G-cheat-postgame: a flip arrives after the game completed           -> rule 3
                       (post-terminal, on a fresh monitor instance)

Watch the three policy cards on the dashboard turn from green to a rendered
violation. The same run also invokes the exit-coded replay gate at the end.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "monitoring"))

from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402

from app.game import MemoryGame, FLIPPED, deal                  # noqa: E402
from steps import build_registry, load_policies                # noqa: E402

HERE = Path(__file__).resolve().parent


def winning_order(deck):
    pairs = {}
    for pos, sym in enumerate(deck):
        pairs.setdefault(sym, []).append(pos)
    return list(pairs.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--monitor-port", type=int, default=7105)
    ap.add_argument("--auto-exit", type=float, default=None,
                    help="exit this many seconds after the scenario (for tests)")
    args = ap.parse_args()

    start = time.time()
    clock = lambda: time.time() - start
    registry = build_registry()
    policies = load_policies(registry)
    dashboard = Dashboard(policies, registry=registry,
                          catalog="monitoring/catalog.json", app=["app/game.py"])
    source = QueueSource()
    emit = lambda e: source.push(dashboard.tap(e))
    engine = Engine(policies, terminal_event_types={"game.completed"}, grace=0.4)
    threading.Thread(target=lambda: engine.run(source, sink=dashboard.sink),
                     daemon=True).start()

    url = dashboard.start(port=args.monitor_port)
    print(f"live monitor: {url}\n")

    def play(game: MemoryGame):
        game.start()
        for a, b in winning_order(game.deck):
            game.flip(a); time.sleep(0.05)
            game.flip(b); time.sleep(0.05)     # instant match

    # -- 1. a healthy game: every card card resolves, all three rules green --
    print("1) healthy game 'demo-ok' -> should stay all green")
    play(MemoryGame("demo-ok", emit, clock, deal(seed=1)))
    time.sleep(0.4)

    # -- 2. rule 1: re-flip a matched card ---------------------------------
    print("2) cheat 'demo-rematch' -> re-flips a matched card (rule 1)")
    g2 = MemoryGame("demo-rematch", emit, clock, deal(seed=2))
    g2.start()
    pair = winning_order(g2.deck)[0]
    g2.flip(pair[0]); g2.flip(pair[1])          # this pair is now matched
    time.sleep(0.1)
    emit(Event(FLIPPED, clock(), {"game_id": "demo-rematch",
               "attempt_id": "demo-rematch-x", "position": pair[0]},
               {"slot": "illegal", "symbol": g2.deck[pair[0]],
                "already_matched": True, "after_completion": False}, "corrupted"))
    time.sleep(0.4)

    # -- 3. rule 2: an attempt left hanging (wall timer fires it) -----------
    print("3) cheat 'demo-hang' -> a second flip that never resolves (rule 2);"
          " waiting for the 3s timer...")
    g3 = MemoryGame("demo-hang", emit, clock, deal(seed=3))
    g3.start()
    emit(Event(FLIPPED, clock(), {"game_id": "demo-hang",
               "attempt_id": "demo-hang-1", "position": 0},
               {"slot": "second", "symbol": "?",
                "already_matched": False, "after_completion": False}, "corrupted"))
    time.sleep(3.4)                              # > 3s: the deadline lapses

    # -- 4. rule 3: activity after completion (post-terminal) --------------
    print("4) cheat 'demo-postgame' -> a flip after the game completed (rule 3)")
    g4 = MemoryGame("demo-postgame", emit, clock, deal(seed=4))
    play(g4)                                     # runs to game.completed
    time.sleep(0.3)
    emit(Event(FLIPPED, clock(), {"game_id": "demo-postgame",
               "attempt_id": "demo-postgame-x", "position": 0},
               {"slot": "illegal", "symbol": g4.deck[0],
                "already_matched": True, "after_completion": True}, "corrupted"))
    time.sleep(0.6)

    counts = dashboard.state()["counts"]
    print(f"\nlive verdicts so far: {counts['verdicts']} "
          f"({counts['violations']} violation(s), {counts['events']} events)")

    # -- the exit-coded replay gate over deterministic traffic -------------
    print("\nrunning the replay gate (deterministic, exit-coded):")
    gate = subprocess.run([sys.executable, str(HERE / "monitoring" / "replay_check.py")],
                          capture_output=True, text=True)
    print(gate.stdout.strip().splitlines()[-1] if gate.stdout else "")
    print(f"replay gate exit code: {gate.returncode}")

    if args.auto_exit is not None:
        time.sleep(args.auto_exit)
        dashboard.stop()
        return 0 if gate.returncode == 0 else 1
    print(f"\nDashboard holding at {url} - Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
