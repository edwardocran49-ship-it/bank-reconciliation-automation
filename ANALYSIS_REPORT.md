# Bank Reconciliation Control Report

## Objective

Demonstrate a reproducible month-end bank-to-general-ledger reconciliation in
which every source row is either paired to a supported counterpart or routed
to a reviewable exception class.

## Control design

The engine performs three deterministic passes. Earlier, stronger evidence
takes precedence and a source row cannot be used twice.

1. **Same-day exact** — equal signed amount and posting date.
2. **Timing difference** — equal signed amount within a configurable clearing
   window.
3. **Controlled variance** — amount difference within tolerance, date within
   the wider window, and supporting reference or description similarity.

Unmatched rows are classified as possible duplicates, outstanding checks,
deposits in transit, unrecorded bank fees or interest, and other items requiring
investigation. The software suggests an action but never posts a journal entry.

## Accounting proof

The control compares adjusted movement for the period:

```text
Bank movement + GL-only reconciling items
    = Adjusted bank movement

GL movement + bank-only items + supported matched variances
    = Adjusted book movement
```

The residual is the difference between those adjusted figures. The included
sample produces a zero residual while preserving a visible exception queue for
accountant review.

## Limitations

- The included files contain period activity rather than independently supplied
  opening and closing balance confirmations.
- Description similarity is deterministic string comparison, not a trained
  model and not a substitute for professional judgment.
- Suggested accounts are review cues, not approved journal entries.
- A production deployment would add user access controls, immutable run
  storage, approval workflow, and direct ERP/bank integrations.
