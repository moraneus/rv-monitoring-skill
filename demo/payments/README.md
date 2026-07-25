# Payment tracker with behave-rv runtime verification

A plain-Python `PaymentService` you drive from code, monitored at runtime by
[behave-rv](https://github.com/moraneus/behave-rv) against three policies you own.

## Lifecycle

```
authorized -> captured -> closed                              (never disputed)
authorized -> captured -> disputed -> investigated -> refunded -> closed
```

A disputed payment is frozen; a customer action on a frozen payment is refused
with a "frozen" rejection.

## Run it

```bash
PY=<path-to>/venv031/bin/python

# live demo + web dashboard (default runs the flows, then exits)
$PY demo.py                 # dashboard at http://127.0.0.1:7205
$PY demo.py --serve         # ... and keep it up to watch (Ctrl+C to stop)

# the deterministic verdict gate (CI)
$PY monitoring/replay_check.py

# the two-sided stability contract (CI)
$PY -m behave_rv catalog diff --steps monitoring/steps.py \
    --catalog monitoring/catalog.json --policies monitoring/policies \
    --app app/service.py --fail-on-app-risk \
    --trace monitoring/traces/representative.jsonl
```

## Layout

- `app/service.py` - the `PaymentService`, instrumented with events at each transition.
- `monitoring/policies/` - your three rules, one `.feature` each.
- `monitoring/steps.py` - the step vocabulary policies bind to; `STEPS.md` is its generated doc.
- `monitoring/catalog.json` - the committed two-sided contract (regenerate only for intended changes).
- `monitoring/replay_check.py` - scripted traffic + exit-coded verdict gate.
- `monitoring/SUGGESTED_POLICIES.md` - my proposals, including a conflict you must resolve.

## The rules

1. Once disputed, no new charge activity (re-authorize / re-capture) may happen
   to a payment; the team's investigate / refund / close is allowed.
2. Every *disputed* payment that closes must have been refunded first; a plain
   (never-disputed) close is free.
3. Once captured, a payment must be closed or disputed within 20 seconds.

An earlier, wider reading of rules 1 and 2 conflicted with the described
lifecycles; both were narrowed to the intended meaning (see
`monitoring/SUGGESTED_POLICIES.md`). Both described healthy flows now run clean
in `replay_check.py` and the demo; `replay_check.py` exits 0.
