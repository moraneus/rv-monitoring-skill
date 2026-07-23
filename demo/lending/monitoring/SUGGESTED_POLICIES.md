# Suggested policies (proposals - you own the decision)

These are drafts. Nothing here is active. To adopt one, move it into
`monitoring/policies/` as its own numbered `.feature` file and rerun the
gates. Each was verified to compile against the current `steps.py`.

---

## Adopted

- **2026-07-23: A renewal restarts the settlement window** - approved and
  now active as `policies/04_renewal_restarts_window.feature`.
- **2026-07-23: A loan is only renewed after it was borrowed** - approved and
  now active as `policies/05_renew_after_borrow.feature`.
- **2026-07-23: A member who owes a fine cannot renew until they pay it off** -
  approved and now active as `policies/06_fines_freeze_renewals.feature`. The
  member-keyed `member.renewal` event that makes this monitorable in-fragment
  is kept. This is a tripwire: it stays `pending` forever while the guard
  holds (members have no terminal event) and only fires `violated` if a future
  change lets a renewal through during an `owed`->`paid_off` interval.

---

## Noted, out of scope for now

- **"No copy is on loan to two members at once" / "a member holds at most N
  loans."** These relate *different* loan entities to each other (or count
  across them). They are cross-entity / aggregate properties, which are out
  of the single-key temporal fragment and cannot be expressed as one
  per-loan scenario. Recorded here as future-fragment material.
- **"Every loan is eventually closed"** (`has happened` on a terminal) is
  in-fragment but only meaningful for loans that emit the terminal. Returns
  emit it; abandoned loans (rule 3 already catches those) and lost loans
  (deliberately kept open, see `TERMINAL_TYPE`) do not, so this policy would
  stay `pending` for them. Not proposed as active until that trade-off is
  something you want.
