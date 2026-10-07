# Dataset

This project uses two deterministic, synthetic CSV files covering June 2026:

- `data/raw/bank_statement_jun2026.csv` — 122 bank transactions.
- `data/raw/gl_cash_extract_jun2026.csv` — 122 general-ledger cash transactions.

The files were obtained from the public
[`raghavkhanna-finance/bank-to-gl-reconciliation`](https://github.com/raghavkhanna-finance/bank-to-gl-reconciliation/tree/main/data)
repository. The source repository describes the data as deterministic and synthetic.
It is licensed under the MIT License; the required copyright and permission
notice is reproduced in `THIRD_PARTY_NOTICES.md`.

## Fields

### Bank statement

| Field | Meaning |
|---|---|
| `Date` | Bank posting date |
| `Description` | Bank transaction narration |
| `Reference` | Bank reference or cheque number |
| `Amount` | Signed amount; receipts are positive and payments are negative |

### GL cash extract

| Field | Meaning |
|---|---|
| `Date` | General-ledger posting date |
| `Account` | Cash account name |
| `Memo` | Book-side transaction description |
| `DocNo` | Document reference or cheque number |
| `Amount` | Signed amount; receipts are positive and payments are negative |

## Intended use

The data supports reproducible demonstrations, accounting education, automated
testing, and portfolio review. It contains no real customer, employee, or bank
account information.
