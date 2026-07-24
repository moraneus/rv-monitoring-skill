"""Scripted demo - no browser needed.

    python demo.py [--dash-port 7105] [--hold] [--no-dashboard]

Plays a few games live through the real engine and the behave-rv dashboard,
then injects corrupted events - re-flipping a matched card, an attempt left
hanging, an action after completion - so every rule is driven to a violation.
Verdicts and their rendered counterexamples print to the console; the same
verdicts land on the dashboard while it runs.

For the exit-coded gate on a recorded stream, see ``monitoring/replay_check.py``.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.event import Event                          # noqa: E402
from behave_rv.events.sources.subscription import QueueSource     # noqa: E402
from behave_rv.dashboard import Dashboard                         # noqa: E402
from behave_rv.verdict.explain import explain_verdict            # noqa: E402

from app.game import (                                            # noqa: E402
    MemoryGame, live_clock, new_order,
    CARD_FLIP, CARD_MATCHED, GAME_ACTION, ATTEMPT_PENDING, SOURCE,
)
from steps import build_registry, load_policies                  # noqa: E402


def pairs_sequence(order):
    seen, seq = {}, []
    for pos, sym in enumerate(order):
        if sym in seen:
            seq += [seen.pop(sym), pos]
        else:
            seen[sym] = pos
    return seq


def play(emit, clock, game_id, seed, pairs=None, pace=0.02):
    order = new_order(seed)
    game = MemoryGame(game_id, emit, clock, order=order)
    game.start()
    clicks = pairs_sequence(order)
    if pairs is not None:
        clicks = clicks[: pairs * 2]
    for pos in clicks:
        game.flip(pos)
        time.sleep(pace)   # let the dashboard animate; keeps events readable
    return game


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dash-port", type=int, default=7105)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--hold", action="store_true",
                    help="keep the dashboard running after the demo for inspection")
    ap.add_argument("--no-dashboard", action="store_true",
                    help="console only; do not start the web dashboard")
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)
    source = QueueSource()
    clock = live_clock()

    verdicts = []
    if args.no_dashboard:
        sink = verdicts.append
        emit = source.push
        dash_url = None
    else:
        dashboard = Dashboard(policies, registry=registry,
                              catalog=str(ROOT / "monitoring" / "catalog.json"),
                              app=[str(ROOT / "app" / "game.py")])

        def sink(v):
            verdicts.append(v)
            dashboard.sink(v)

        def emit(e):
            source.push(dashboard.tap(e))
        dash_url = dashboard.start(port=args.dash_port, host=args.host)

    engine = Engine(policies, terminal_event_types={"attempt.resolved"}, grace=0.5)
    threading.Thread(target=engine.run, args=(source,),
                     kwargs={"sink": sink}, daemon=True).start()

    if dash_url:
        print(f"live monitor: {dash_url}  (open it to watch the verdicts arrive)\n")

    print("playing two healthy games ...")
    play(emit, clock, "demo-healthy-1", seed=11)
    g2 = play(emit, clock, "demo-healthy-2", seed=22)

    print("cheat 1/3: re-flipping a card that is already matched (rule 1) ...")
    matched_pos = next(i for i, c in g2.cards.items() if c.matched)
    emit(Event(CARD_FLIP, clock(),
               {"game_id": "demo-healthy-2", "position": matched_pos},
               {"symbol": g2.cards[matched_pos].symbol,
                "attempt_id": "demo-healthy-2-cheat"}, SOURCE))

    print("cheat 2/3: an action after the game is complete (rule 3) ...")
    emit(Event(GAME_ACTION, clock(), {"game_id": "demo-healthy-2"},
               {"kind": "ghost"}, SOURCE))

    print("cheat 3/4: a card reported matched with no preceding flip (rule 4) ...")
    emit(Event(CARD_MATCHED, clock(),
               {"game_id": "demo-phantom", "position": 0},
               {"symbol": "ghost", "attempt_id": "demo-phantom-cheat"}, SOURCE))

    print("cheat 4/4: a second card flipped whose attempt never resolves (rule 2) ...")
    emit(Event(ATTEMPT_PENDING, clock(), {"attempt_id": "demo-hang"},
               {"game_id": "demo-cheat", "first": 0, "second": 1}, SOURCE))

    print("\nwaiting for the 3-second deadline timer to fire ...")
    time.sleep(4.0)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]
    print(f"\n=== {len(violations)} violation(s) detected ===\n")
    for v in violations:
        policy = by_id[v.policy_id]
        print(explain_verdict(v, policy.authored_scenario,
                              policy.failing_step_index))
        print("-" * 66)

    satisfied = sum(1 for v in verdicts if v.verdict == "satisfied")
    print(f"\n(also {satisfied} attempts satisfied on the healthy games)")
    print("replay gate with pinned expectations: python monitoring/replay_check.py")

    if args.hold and dash_url:
        print(f"\ndashboard held open at {dash_url} - Ctrl-C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
