# tools

Coverage-confidence tooling for the demos (and any behave-rv project).

- **`monitor_kill_rate.py`** - mutation testing where the app is the subject and
  the monitor is the test suite. Mutates an app file and, per mutant, runs the
  demo's `monitoring/replay_check.py`; a mutant is killed when the gate goes red.
  Reports the runtime kill rate and the survivors (the monitor's blind spots).
- **`run_kill_rates.py`** - runs the harness over every `demo/*/` and writes
  `kill_rates.json` plus a summary. See `MONITOR_KILL_RATE.md` for the results
  and how the metric composes with `catalog coverage` into a coverage-confidence
  loop.

```
uv run --no-project --with behave-rv==0.5.0 python tools/run_kill_rates.py
```
