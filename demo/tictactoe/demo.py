"""Scripted tic-tac-toe demo - no browser required.

Plays a handful of games through the real ``GameService`` while a live
behave-rv dashboard watches, then prints the authoritative verdicts with
their rendered explanations. Two of the games contain CORRUPTED events -
events that bypass the service, as a compromised producer would - to show
the monitor catching what the game code itself never emits:

  * a double move by the same player            -> law 1 violated
  * a move after the game was already won        -> law 2 violated
  * a game abandoned before it was decided        -> law 3 violated

    python demo.py                # play, then hold the dashboard up (Ctrl+C)
    python demo.py --linger 0     # play, print verdicts, exit immediately

Dashboard: http://127.0.0.1:7104 (--dash-port to change).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.engine.loop import Engine                        # noqa: E402
from behave_rv.events.sources.subscription import QueueSource   # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource  # noqa: E402
from behave_rv.events.event import Event                        # noqa: E402
from behave_rv.dashboard import Dashboard                       # noqa: E402
from behave_rv.verdict.explain import explain_verdict           # noqa: E402
import threading                                                # noqa: E402

from steps import build_registry, load_policies, STATUS, OVER   # noqa: E402
from app.game import GameService                                # noqa: E402

X_WIN = [0, 3, 1, 4, 2]                 # X takes the top row
DRAW = [3, 5, 2, 1, 8, 4, 0, 6, 7]      # a verified cat's game
PACE = 0.45                             # seconds between visible actions


def banner(text: str) -> None:
    print(f"\n\033[1m{text}\033[0m")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dash-port", type=int, default=7104)
    parser.add_argument("--linger", type=float, default=None,
                        help="seconds to hold the dashboard after playing "
                             "(default: hold until Ctrl+C)")
    parser.add_argument("--pace", type=float, default=PACE)
    args = parser.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    # Live side: dashboard watches events as they happen.
    live_source = QueueSource()
    dashboard = Dashboard(policies, registry=registry,
                          catalog=str(ROOT / "monitoring" / "catalog.json"),
                          app=[str(ROOT / "app" / "game.py")])
    live_engine = Engine(policies, terminal_event_types={OVER}, grace=0.5)
    threading.Thread(target=lambda: live_engine.run(live_source, sink=dashboard.sink),
                     daemon=True).start()
    url = dashboard.start(port=args.dash_port)

    # Record every event for the authoritative post-hoc replay verdicts.
    recorded: list[Event] = []
    start = time.time()
    clock = lambda: time.time() - start

    def emit(event: Event) -> None:
        recorded.append(event)
        live_source.push(dashboard.tap(event))

    svc = GameService(emit, clock=clock)

    print("=" * 62)
    print(f"  live monitor: {url}")
    print("  open it now - the five games below will play into it live")
    print("=" * 62)

    def play(cells):
        for c in cells:
            svc.play(c)
            time.sleep(args.pace)

    def corrupt(gid, payload, label):
        print(f"    >> injecting corrupted event: {label}")
        emit(Event(STATUS, svc._now(), {"game_id": gid},
                   {"status": "move", **payload}, "corrupted"))
        time.sleep(args.pace)

    banner("Game 1 - a clean win (X takes the top row)")
    svc.new_game(); play(X_WIN)

    banner("Game 2 - a clean draw (cat's game)")
    svc.new_game(); play(DRAW)

    banner("Game 3 - LAW 1: a double move by X, injected mid-game")
    gid = svc.new_game(); play([0])
    corrupt(gid, {"player": "X", "prev_player": "X", "after_finish": "no",
                  "move_number": "99"}, "X moves twice in a row")
    play([3, 1, 4, 2])           # legal play resumes and the game still finishes

    banner("Game 4 - LAW 2: a move after the game was already won")
    gid = svc.new_game(); play(X_WIN)     # X wins; game.over fires
    corrupt(gid, {"player": "O", "prev_player": "X", "after_finish": "yes",
                  "move_number": "99"}, "a move lands on a decided board")

    banner("Game 5 - LAW 3: a game abandoned before it finishes")
    svc.new_game(); play([4, 0])          # in progress...
    print("    >> starting a new game while the last one is unfinished")
    svc.new_game(); play(X_WIN)           # abandons the previous game, then finishes

    time.sleep(1.0)                       # let the live grace window flush

    # Authoritative verdicts: replay the recorded stream deterministically.
    banner("Verdicts (replay of the recorded stream)")
    r2 = build_registry()
    p2 = load_policies(r2)
    rsrc = InProcessSource()
    for e in recorded:
        rsrc.emit(e)
    verdicts = Engine(p2, terminal_event_types={OVER}).run(rsrc, emit_pending=True)
    by_id = {p.policy_id: p for p in p2}
    violations = [v for v in verdicts if v.verdict == "violated"]
    for v in verdicts:
        mark = {"satisfied": "\033[32m", "violated": "\033[31m",
                "pending": "\033[33m"}.get(v.verdict, "")
        print(f"  {mark}{v.verdict:9}\033[0m  {v.entity_key}  {v.policy_id}")
    for v in violations:
        p = by_id[v.policy_id]
        print()
        print(explain_verdict(v, p.authored_scenario, p.failing_step_index))
    print(f"\n{len(verdicts)} verdicts, {len(violations)} violation(s) "
          f"(expected 3: one per law)")

    live_source.close()
    if args.linger is None:
        print(f"\nDashboard still live at {url} - Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    elif args.linger > 0:
        print(f"\nDashboard live at {url} for {args.linger:.0f}s...")
        time.sleep(args.linger)
    dashboard.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
