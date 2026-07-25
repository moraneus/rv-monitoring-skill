"""Scripted Blackjack demo - no browser needed.

Plays several hands through the real table and injects cheats as corrupted
events (a card dealt after stand, a busted hand settled as a win, an unfinished
hand, a payout before settlement). Runs the same deterministic engine the live
game uses and prints every verdict with the failing step and deciding events -
this console output IS the replay gate.

    python demo.py                # headless: print verdicts + explanations
    python demo.py --dashboard    # also serve the live monitor to watch

With --dashboard the same verdicts appear on the behave-rv dashboard (default
http://127.0.0.1:7102); Ctrl-C to stop.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))

from behave_rv.engine.loop import Engine                          # noqa: E402
from behave_rv.events.sources.inprocess import InProcessSource     # noqa: E402
from behave_rv.verdict.explain import explain_verdict              # noqa: E402

from steps import build_registry, load_policies                   # noqa: E402
from app.scenarios import build_scripted_traffic, CHEATS          # noqa: E402
from monitoring.replay_check import FakeClock, TERMINAL_TYPES     # noqa: E402

RULE_TITLES = {
    "rule 1": "Once a hand stands, it is never dealt another card.",
    "rule 2": "A hand that busts is never settled as a win.",
    "rule 3": "Every dealt hand reaches settlement within 30 seconds.",
    "rule 4": "A payout only ever happens after settlement.",
    "rule 5": "A hand settled as a loss is never paid out.",
}
RULE_KEYS = ("rule 1", "rule 2", "rule 3", "rule 4", "rule 5")


def hr(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", action="store_true",
                    help="serve the live monitor while replaying")
    ap.add_argument("--dash-port", type=int, default=7102)
    args = ap.parse_args()

    registry = build_registry()
    policies = load_policies(registry)

    source = InProcessSource()
    clock = FakeClock()
    hr("Table rules being verified")
    for key in RULE_KEYS:
        print(f"  {key}: {RULE_TITLES[key]}")

    hr("Dealing the scripted hands (healthy + injected cheats)")
    log = build_scripted_traffic(source.emit, clock)
    for label, detail in log:
        print(f"  {label:15} {detail}")

    dashboard = None
    if args.dashboard:
        from behave_rv.dashboard import Dashboard
        dashboard = Dashboard(policies, registry=registry,
                              catalog=str(ROOT / "monitoring" / "catalog.json"),
                              app=[str(ROOT / "app" / "blackjack.py")])
        url = dashboard.start(port=args.dash_port)
        print(f"\nlive monitor: {url}")

    engine = Engine(policies, terminal_event_types=TERMINAL_TYPES, grace=0.5)
    verdicts = engine.run(source, emit_pending=True,
                          sink=dashboard.sink if dashboard else None)

    by_id = {p.policy_id: p for p in policies}
    violations = [v for v in verdicts if v.verdict == "violated"]

    hr(f"Verdicts: {len(verdicts)} total, {len(violations)} violation(s)")
    for v in violations:
        hand = v.entity_key.get("hand_id", "?")
        rule, what = CHEATS.get(hand, ("", ""))
        tag = f"[{rule}] " if rule else ""
        print(f"\n{tag}hand {hand}: {what}")
        policy = by_id[v.policy_id]
        print(explain_verdict(v, policy.authored_scenario, policy.failing_step_index))

    hr("Summary")
    caught = {CHEATS[v.entity_key.get('hand_id')][0]
              for v in violations if v.entity_key.get('hand_id') in CHEATS}
    for key in RULE_KEYS:
        mark = "VIOLATION CAUGHT" if key in caught else "ok"
        print(f"  {key}: {mark}")
    print("\nTerminal-window note: the three scoped prohibitions (rules 1, 2, 5)")
    print("are only armed until a hand.closed terminal settles them. The three")
    print("'window probe' seeds inject a forbidden event AFTER close, so those")
    print("prohibitions (correctly) do NOT flag them - that marks the real")
    print("detection window. One bonus: the rule-5 probe's post-close payout is")
    print("still caught - by rule 4 - because to a fresh post-terminal hand a")
    print("payout with nothing settled-before is a payout-before-settlement.")

    if dashboard:
        print(f"\nlive monitor still up at port {args.dash_port} - Ctrl-C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            dashboard.stop()

    return 0 if caught == set(RULE_KEYS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
