# Class-booking runtime monitoring

Runtime verification for a small fitness studio's class bookings, built with
[behave-rv](https://github.com/moraneus/behave-rv). The monitor watches the
live event stream of the booking service and, per booking (and per member),
reports which of your policies is satisfied, violated, or still pending - and
for every violation, replays your own scenario with the real booking's events.

## Watch it live

```bash
python live_monitor.py            # serves ~35s of seeded traffic
# open the printed URL, default http://127.0.0.1:7007
```

The dashboard shows each policy as a card with its per-booking verdicts, the
explanation for every violation, the live event feed, and a strip confirming
the code still matches the committed contract. The seeded traffic deliberately
trips the cancelled-then-checked-in rule, the balance-owed rule, and the 15s
promotion deadline (the last one fires ~15s in, from the engine's timer, with
nothing else happening).

## Check policies against recorded traffic (the gate)

```bash
python monitoring/replay_check.py        # exit 0 when verdicts match the pin
```

## The two-sided contract

```bash
python -m behave_rv catalog diff \
  --steps monitoring/steps.py --catalog monitoring/catalog.json \
  --policies monitoring/policies --app app/booking_service.py \
  --fail-on-app-risk --trace monitoring/traces/replay_check.jsonl
```

## Layout

```
app/booking_service.py      the studio's booking logic, with event taps
monitoring/
  steps.py                  the vocabulary your policies are written in
  policies/                 your policies (one Feature per file)
  catalog.json              the committed contract between code and policies
  STEPS.md                  generated vocabulary reference (do not hand-edit)
  SUGGESTED_POLICIES.md     proposals you can adopt or reject
  replay_check.py           the deterministic verdict gate
  traces/                   recorded event streams
live_monitor.py             run the app live with the dashboard attached
```

## Your policies

| # | File | Rule |
|---|------|------|
| 01 | cancelled_never_checked_in | a cancelled booking is never checked in |
| 02 | check_in_requires_confirmation | a booking is only checked in after it was confirmed |
| 03 | no_confirm_while_balance_owed | a member who owes a balance gets no booking confirmed (per member) |
| 04 | promotion_deadline | a promoted booking is confirmed or cancelled within 15 seconds |
| 05 | attended_after_check_in | a booking is only attended after it was checked in |
| 06 | every_booking_resolves | every booking eventually reaches a final state (still-waiting light) |
```
