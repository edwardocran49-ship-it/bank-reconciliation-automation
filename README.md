# Bank Reconciliation Automation

An auditable Python and Streamlit application that reconciles a synthetic bank
statement to a general-ledger cash extract, isolates month-end exceptions, and
exports a review-ready Excel workbook.

## Portfolio outcome

This project demonstrates accounting control design, deterministic transaction
matching, exception management, data validation, automated testing, and
management reporting. Every source row remains traceable to its original CSV
line.

## What the application does

- Matches same-day transactions with equal signed amounts.
- Identifies clearing-date differences within a configurable window.
- Resolves small controlled amount variances using reference and description
  evidence.
- Prevents a bank or GL row from being matched more than once.
- Classifies outstanding checks, deposits in transit, possible duplicates,
  bank fees, interest, and unidentified bank activity.
- Produces a formal adjusted-bank versus adjusted-book control proof.
- Exports summary, match, exception, suggested-entry, and source-data sheets to
  Excel.

## Visual direction

The dashboard uses an Industrial control-room direction: pitch-black surfaces,
amber control signals, monospaced typography, flat one-pixel borders, and
tabular figures. The signature element is the reconciliation proof strip, which
places the adjusted bank and book figures side by side and keeps the residual
visible throughout review.

## Run locally

Use Python 3.11 or newer.

```powershell
git clone https://github.com/edwardocran49-ship-it/bank-reconciliation-automation.git
cd bank-reconciliation-automation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The included June 2026 sample loads automatically. Upload both CSVs from the
sidebar to run a different reconciliation with the documented schemas.

## Run the tests

```powershell
python -m pytest -q
```

The tests verify matching controls, one-to-one row usage, full row disposition,
exception handling, accounting equality, and workbook generation.

## Project structure

```text
bank-reconciliation-automation/
├── .github/workflows/test.yml
├── app.py
├── bank_recon/
│   ├── engine.py
│   └── reporting.py
├── data/raw/
│   ├── bank_statement_jun2026.csv
│   └── gl_cash_extract_jun2026.csv
├── tests/
├── ANALYSIS_REPORT.md
├── DATASET.md
├── LICENSE
└── THIRD_PARTY_NOTICES.md
```

## Data and attribution

The input files are deterministic synthetic data from the MIT-licensed
[`raghavkhanna-finance/bank-to-gl-reconciliation`](https://github.com/raghavkhanna-finance/bank-to-gl-reconciliation/tree/main/data)
repository. See [DATASET.md](DATASET.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The application logic and
interface in this folder are original implementations.

## License

The original application code is released under the MIT License. The bundled
synthetic source data retains its original MIT notice in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Accounting limitations

The application supports review; it does not automatically approve matches or
post journals. The sample proves period movement because the public files do
not include independently confirmed opening and closing bank balances.
