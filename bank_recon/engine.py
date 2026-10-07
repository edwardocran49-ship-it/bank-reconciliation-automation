"""Deterministic, auditable bank-to-GL reconciliation logic."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Callable

import pandas as pd


BANK_COLUMNS = {"Date", "Description", "Reference", "Amount"}
GL_COLUMNS = {"Date", "Account", "Memo", "DocNo", "Amount"}


@dataclass(frozen=True)
class ReconciliationConfig:
    """Controls for the deterministic matching passes."""

    timing_window_days: int = 5
    fuzzy_window_days: int = 7
    amount_tolerance: float = 0.99
    description_threshold: float = 0.35


@dataclass
class ReconciliationResult:
    """All reconciliation outputs, including the accounting proof."""

    matches: pd.DataFrame
    exceptions: pd.DataFrame
    bank: pd.DataFrame
    gl: pd.DataFrame
    bank_balance: float
    gl_balance: float
    bank_only_adjustments: float
    duplicate_reversals: float
    bank_adjustments: float
    book_adjustments: float
    matched_variance: float
    adjusted_bank_balance: float
    adjusted_book_balance: float
    residual: float

    @property
    def total_source_rows(self) -> int:
        return len(self.bank) + len(self.gl)

    @property
    def matched_source_rows(self) -> int:
        return len(self.matches) * 2

    @property
    def match_rate(self) -> float:
        if not self.total_source_rows:
            return 0.0
        return self.matched_source_rows / self.total_source_rows

    @property
    def is_reconciled(self) -> bool:
        return abs(self.residual) < 0.005


def _normalise_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value).upper().strip()
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _normalise_reference(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", _normalise_text(value))


def _validate_columns(frame: pd.DataFrame, expected: set[str], label: str) -> None:
    missing = sorted(expected.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def _prepare_bank(frame: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(frame, BANK_COLUMNS, "Bank statement")
    prepared = pd.DataFrame(
        {
            "row_id": [f"BANK-{number:04d}" for number in range(1, len(frame) + 1)],
            "source_row": range(2, len(frame) + 2),
            "date": pd.to_datetime(frame["Date"], errors="raise").dt.normalize(),
            "description": frame["Description"].fillna("").astype(str),
            "reference": frame["Reference"].fillna("").astype(str),
            "amount": pd.to_numeric(frame["Amount"], errors="raise").astype(float),
        }
    )
    prepared["normalised_description"] = prepared["description"].map(_normalise_text)
    prepared["normalised_reference"] = prepared["reference"].map(_normalise_reference)
    return prepared.set_index("row_id", drop=False)


def _prepare_gl(frame: pd.DataFrame) -> pd.DataFrame:
    _validate_columns(frame, GL_COLUMNS, "GL cash extract")
    prepared = pd.DataFrame(
        {
            "row_id": [f"GL-{number:04d}" for number in range(1, len(frame) + 1)],
            "source_row": range(2, len(frame) + 2),
            "date": pd.to_datetime(frame["Date"], errors="raise").dt.normalize(),
            "account": frame["Account"].fillna("").astype(str),
            "description": frame["Memo"].fillna("").astype(str),
            "reference": frame["DocNo"].fillna("").astype(str),
            "amount": pd.to_numeric(frame["Amount"], errors="raise").astype(float),
        }
    )
    prepared["normalised_description"] = prepared["description"].map(_normalise_text)
    prepared["normalised_reference"] = prepared["reference"].map(_normalise_reference)
    return prepared.set_index("row_id", drop=False)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _candidate_metrics(bank_row: pd.Series, gl_row: pd.Series) -> dict[str, float | bool]:
    date_delta = abs((bank_row["date"] - gl_row["date"]).days)
    amount_delta = abs(float(bank_row["amount"]) - float(gl_row["amount"]))
    ref_exact = bool(
        bank_row["normalised_reference"]
        and bank_row["normalised_reference"] == gl_row["normalised_reference"]
    )
    ref_similarity = _similarity(
        str(bank_row["normalised_reference"]), str(gl_row["normalised_reference"])
    )
    description_similarity = _similarity(
        str(bank_row["normalised_description"]), str(gl_row["normalised_description"])
    )
    return {
        "date_delta": date_delta,
        "amount_delta": amount_delta,
        "ref_exact": ref_exact,
        "ref_similarity": ref_similarity,
        "description_similarity": description_similarity,
    }


def _run_pass(
    bank: pd.DataFrame,
    gl: pd.DataFrame,
    available_bank: set[str],
    available_gl: set[str],
    pass_name: str,
    eligible: Callable[[dict[str, float | bool]], bool],
    ranker: Callable[[dict[str, float | bool]], float],
    confidence: Callable[[dict[str, float | bool]], int],
) -> list[dict[str, object]]:
    candidates: list[tuple[float, str, str, dict[str, float | bool]]] = []
    for bank_id in sorted(available_bank):
        for gl_id in sorted(available_gl):
            metrics = _candidate_metrics(bank.loc[bank_id], gl.loc[gl_id])
            if eligible(metrics):
                candidates.append((ranker(metrics), bank_id, gl_id, metrics))

    candidates.sort(
        key=lambda item: (
            -item[0],
            int(item[3]["date_delta"]),
            float(item[3]["amount_delta"]),
            item[1],
            item[2],
        )
    )

    selected: list[dict[str, object]] = []
    used_bank: set[str] = set()
    used_gl: set[str] = set()
    for _, bank_id, gl_id, metrics in candidates:
        if bank_id in used_bank or gl_id in used_gl:
            continue
        used_bank.add(bank_id)
        used_gl.add(gl_id)
        selected.append(
            _match_record(
                bank.loc[bank_id],
                gl.loc[gl_id],
                pass_name,
                confidence(metrics),
                metrics,
            )
        )

    available_bank.difference_update(used_bank)
    available_gl.difference_update(used_gl)
    return selected


def _match_record(
    bank_row: pd.Series,
    gl_row: pd.Series,
    pass_name: str,
    confidence: int,
    metrics: dict[str, float | bool],
) -> dict[str, object]:
    return {
        "match_method": pass_name,
        "confidence": confidence,
        "date_difference_days": int(metrics["date_delta"]),
        "amount_variance": round(float(bank_row["amount"] - gl_row["amount"]), 2),
        "bank_row_id": bank_row["row_id"],
        "bank_source_row": int(bank_row["source_row"]),
        "bank_date": bank_row["date"],
        "bank_description": bank_row["description"],
        "bank_reference": bank_row["reference"],
        "bank_amount": float(bank_row["amount"]),
        "gl_row_id": gl_row["row_id"],
        "gl_source_row": int(gl_row["source_row"]),
        "gl_date": gl_row["date"],
        "gl_description": gl_row["description"],
        "gl_reference": gl_row["reference"],
        "gl_amount": float(gl_row["amount"]),
    }


def _exception_record(
    row: pd.Series,
    source: str,
    duplicate_key_counts: pd.Series,
) -> dict[str, object]:
    key = (row["normalised_reference"], round(float(row["amount"]), 2))
    is_duplicate = bool(row["normalised_reference"] and duplicate_key_counts.get(key, 0) > 1)
    amount = float(row["amount"])
    text = f"{row['normalised_description']} {row['normalised_reference']}"

    if is_duplicate:
        category = "Possible duplicate"
        action = "Confirm the repeated posting and reverse it if it is not supported."
        suggested_account = "Review required"
    elif source == "GL" and amount < 0 and row["normalised_reference"].startswith("CHQ"):
        category = "Outstanding check"
        action = "Carry forward and verify clearance on the next bank statement."
        suggested_account = "No journal entry"
    elif source == "GL" and amount > 0:
        category = "Deposit in transit"
        action = "Carry forward and verify the deposit clears after period end."
        suggested_account = "No journal entry"
    elif source == "GL":
        category = "GL-only transaction"
        action = "Inspect supporting documentation and confirm bank processing."
        suggested_account = "Review required"
    elif amount < 0 and any(token in text for token in ("FEE", "CHARGE", "SERVICE")):
        category = "Bank fee not recorded"
        action = "Record the expense and credit cash after approval."
        suggested_account = "Bank fees"
    elif amount > 0 and "INTEREST" in text:
        category = "Interest income not recorded"
        action = "Record interest income and debit cash after approval."
        suggested_account = "Interest income"
    elif source == "BANK" and amount < 0:
        category = "Unidentified bank debit"
        action = "Investigate the payee, obtain support, and record or dispute the debit."
        suggested_account = "Suspense pending review"
    else:
        category = "Unidentified bank credit"
        action = "Identify the remitter and record the receipt to the correct account."
        suggested_account = "Suspense pending review"

    return {
        "source": source,
        "row_id": row["row_id"],
        "source_row": int(row["source_row"]),
        "date": row["date"],
        "description": row["description"],
        "reference": row["reference"],
        "amount": amount,
        "category": category,
        "recommended_action": action,
        "suggested_account": suggested_account,
        "exposure": abs(amount),
    }


def reconcile(
    bank_statement: pd.DataFrame,
    gl_cash_extract: pd.DataFrame,
    config: ReconciliationConfig | None = None,
) -> ReconciliationResult:
    """Reconcile a bank statement to a GL cash extract without mutating inputs."""

    config = config or ReconciliationConfig()
    bank = _prepare_bank(bank_statement.copy())
    gl = _prepare_gl(gl_cash_extract.copy())
    available_bank = set(bank.index)
    available_gl = set(gl.index)
    records: list[dict[str, object]] = []

    records.extend(
        _run_pass(
            bank,
            gl,
            available_bank,
            available_gl,
            "Same-day exact",
            lambda m: m["date_delta"] == 0 and m["amount_delta"] < 0.005,
            lambda m: 5.0 * float(m["ref_exact"])
            + float(m["description_similarity"]),
            lambda m: 100 if m["ref_exact"] else 96,
        )
    )
    records.extend(
        _run_pass(
            bank,
            gl,
            available_bank,
            available_gl,
            "Timing difference",
            lambda m: m["amount_delta"] < 0.005
            and 0 < m["date_delta"] <= config.timing_window_days,
            lambda m: 5.0 * float(m["ref_exact"])
            + float(m["description_similarity"])
            + (config.timing_window_days - int(m["date_delta"])) / 10,
            lambda m: max(85, 95 - int(m["date_delta"])),
        )
    )
    records.extend(
        _run_pass(
            bank,
            gl,
            available_bank,
            available_gl,
            "Controlled variance",
            lambda m: 0.005 <= m["amount_delta"] <= config.amount_tolerance
            and m["date_delta"] <= config.fuzzy_window_days
            and (
                bool(m["ref_exact"])
                or float(m["description_similarity"]) >= config.description_threshold
                or float(m["ref_similarity"]) >= 0.80
            ),
            lambda m: 5.0 * float(m["ref_exact"])
            + float(m["description_similarity"])
            + float(m["ref_similarity"])
            - float(m["amount_delta"]) / max(config.amount_tolerance, 0.01),
            lambda m: max(
                70,
                round(
                    90
                    - 10 * float(m["amount_delta"]) / max(config.amount_tolerance, 0.01)
                    - int(m["date_delta"])
                ),
            ),
        )
    )

    matches = pd.DataFrame(records)
    if not matches.empty:
        matches.insert(0, "match_id", [f"MATCH-{n:04d}" for n in range(1, len(matches) + 1)])

    bank_keys = bank.apply(
        lambda row: (row["normalised_reference"], round(float(row["amount"]), 2)), axis=1
    ).value_counts()
    gl_keys = gl.apply(
        lambda row: (row["normalised_reference"], round(float(row["amount"]), 2)), axis=1
    ).value_counts()
    exceptions = [
        _exception_record(bank.loc[row_id], "BANK", bank_keys)
        for row_id in sorted(available_bank)
    ]
    exceptions.extend(
        _exception_record(gl.loc[row_id], "GL", gl_keys)
        for row_id in sorted(available_gl)
    )
    exception_frame = pd.DataFrame(exceptions)
    if not exception_frame.empty:
        exception_frame = exception_frame.sort_values(
            ["exposure", "source_row"], ascending=[False, True]
        ).reset_index(drop=True)
        exception_frame.insert(
            0, "exception_id", [f"EXC-{n:03d}" for n in range(1, len(exception_frame) + 1)]
        )

    bank_balance = round(float(bank["amount"].sum()), 2)
    gl_balance = round(float(gl["amount"].sum()), 2)
    gl_exceptions = (
        exception_frame.loc[exception_frame["source"] == "GL"]
        if not exception_frame.empty
        else pd.DataFrame()
    )
    bank_adjustments = round(float(
        gl_exceptions.loc[gl_exceptions["category"] != "Possible duplicate", "amount"].sum()
        if not gl_exceptions.empty
        else 0.0
    ), 2)
    bank_only_adjustments = round(float(
        exception_frame.loc[exception_frame["source"] == "BANK", "amount"].sum()
        if not exception_frame.empty
        else 0.0
    ), 2)
    matched_variance = round(
        float(matches["amount_variance"].sum() if not matches.empty else 0.0), 2
    )
    duplicate_reversals = round(float(
        -gl_exceptions.loc[gl_exceptions["category"] == "Possible duplicate", "amount"].sum()
        if not gl_exceptions.empty
        else 0.0
    ), 2)
    book_adjustments = round(
        bank_only_adjustments + duplicate_reversals + matched_variance, 2
    )
    adjusted_bank_balance = round(bank_balance + bank_adjustments, 2)
    adjusted_book_balance = round(gl_balance + book_adjustments, 2)
    residual = round(adjusted_bank_balance - adjusted_book_balance, 2)

    return ReconciliationResult(
        matches=matches,
        exceptions=exception_frame,
        bank=bank.reset_index(drop=True),
        gl=gl.reset_index(drop=True),
        bank_balance=bank_balance,
        gl_balance=gl_balance,
        bank_only_adjustments=bank_only_adjustments,
        duplicate_reversals=duplicate_reversals,
        bank_adjustments=bank_adjustments,
        book_adjustments=book_adjustments,
        matched_variance=matched_variance,
        adjusted_bank_balance=adjusted_bank_balance,
        adjusted_book_balance=adjusted_book_balance,
        residual=residual,
    )
