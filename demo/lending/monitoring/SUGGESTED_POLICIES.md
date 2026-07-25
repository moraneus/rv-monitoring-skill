# Suggested policies

Proposals only. You own the policies: move an entry into
`monitoring/policies/` yourself if you want it monitored. Each entry below
compiles against the current vocabulary and produces zero violations on the
healthy flows described in the request.

---

## Adopted (2026-07-25)

Both suggestions below were approved by the user and are now live policies:

- "a loan is renewed only after it was borrowed" -> `policies/04_renew_after_borrow.feature`
- "a returned loan is never renewed" -> `policies/05_returned_never_renewed.feature`

Their healthy and fault flows are seeded in `replay_check.py`; the returned
-never-renewed fault arrives through the real borrow -> return -> renew path,
after the close.

---

## Out of fragment (noted, not proposed)

- **"A book copy is never borrowed twice at once."** This relates two loans of
  the same copy (a cross-entity relation on `book_copy_id`), which the
  single-key fragment cannot express as written. It could become in-fragment by
  re-keying: emit a copy-keyed availability event (`copy.status` keyed on
  `book_copy_id`) and write a prohibition over that. That is additive
  instrumentation on a different key; say the word and I will draft it.
- **"No loan is renewed more than N times."** Counting/aggregate - out of
  fragment. The nearest in-fragment shape is a per-loan `within`-style deadline
  or an app-side counter that emits a dedicated `renew.limit_exceeded` marker
  event a self-contained `never` can watch.
