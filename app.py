"""Streamlit dashboard for the bank reconciliation project."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from bank_recon import ReconciliationConfig, build_excel_report, reconcile


ROOT = Path(__file__).resolve().parent
SAMPLE_BANK = ROOT / "data" / "raw" / "bank_statement_jun2026.csv"
SAMPLE_GL = ROOT / "data" / "raw" / "gl_cash_extract_jun2026.csv"
POWER_BI_DASHBOARD = ROOT / "dashboard.html"


st.set_page_config(
    page_title="Bank Reconciliation Automation",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: "IBM Plex Mono", "JetBrains Mono", Consolas, monospace;
        font-variant-numeric: tabular-nums;
    }
    [data-testid="stAppViewContainer"] { background: #000000; color: #F2F2EF; }
    [data-testid="stHeader"] { background: #000000; }
    [data-testid="stSidebar"] { background: #0B0C0A; border-right: 1px solid #FFB800; }
    .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 4rem; }
    h1, h2, h3, p, label, div { color: #F2F2EF; }
    h1 { font-size: clamp(2.2rem, 5vw, 5.8rem); line-height: .92; letter-spacing: -.06em; }
    h2 { border-top: 1px solid #45443F; padding-top: 1rem; margin-top: 2.5rem; }
    .eyebrow { color: #FFB800; font-size: .78rem; letter-spacing: .15em; margin-bottom: .8rem; }
    .period { color: #A09E94; margin-top: -.6rem; }
    .status-line { border: 1px solid #FFB800; padding: .8rem 1rem; color: #FFB800; margin: 1.5rem 0; }
    .proof-grid { display: grid; grid-template-columns: repeat(5, 1fr); border: 1px solid #45443F; margin: 1.5rem 0 2rem; }
    .proof-cell { padding: 1rem; border-right: 1px solid #45443F; min-height: 112px; }
    .proof-cell:last-child { border-right: 0; }
    .proof-label { color: #A09E94; font-size: .72rem; min-height: 36px; }
    .proof-value { color: #F2F2EF; font-size: clamp(1rem, 1.8vw, 1.7rem); margin-top: .5rem; }
    .proof-value.signal { color: #00E676; }
    [data-testid="stMetric"] { background: #0B0C0A; border: 1px solid #45443F; padding: 1rem; }
    [data-testid="stMetricLabel"] { color: #A09E94; }
    [data-testid="stMetricValue"] { color: #F2F2EF; font-size: 1.35rem; }
    .stButton > button, .stDownloadButton > button {
        background: #FFB800; color: #000000; border: 1px solid #FFB800;
        border-radius: 0; font-weight: 700; width: 100%;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: #000000; color: #FFB800; border-color: #FFB800;
    }
    [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid #45443F; }
    [data-baseweb="tab"] { border-radius: 0; border: 1px solid #45443F; border-bottom: 0; }
    [data-baseweb="tab-highlight"] { background: #FFB800; }
    [data-testid="stDataFrame"] { border: 1px solid #45443F; }
    @media (max-width: 900px) {
        .proof-grid { grid-template-columns: 1fr; }
        .proof-cell { border-right: 0; border-bottom: 1px solid #45443F; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"


def compact_money(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.1f}K"
    return money(value)


def read_input(upload, sample_path: Path) -> pd.DataFrame:
    if upload is None:
        return pd.read_csv(sample_path)
    return pd.read_csv(upload)


with st.sidebar:
    st.header("Reconciliation controls")
    st.caption("Upload both files or use the included June 2026 sample.")
    bank_upload = st.file_uploader("Bank statement", type=["csv"], key="bank")
    gl_upload = st.file_uploader("GL cash extract", type=["csv"], key="gl")
    timing_window = st.slider("Timing window (days)", 1, 10, 5)
    amount_tolerance = st.number_input(
        "Amount tolerance", min_value=0.00, max_value=10.00, value=0.99, step=0.01
    )
    description_threshold = st.slider(
        "Description similarity", 0.00, 1.00, 0.35, 0.05
    )
    st.caption("Source data is synthetic and licensed under MIT.")

try:
    bank_input = read_input(bank_upload, SAMPLE_BANK)
    gl_input = read_input(gl_upload, SAMPLE_GL)
    result = reconcile(
        bank_input,
        gl_input,
        ReconciliationConfig(
            timing_window_days=timing_window,
            fuzzy_window_days=max(7, timing_window),
            amount_tolerance=float(amount_tolerance),
            description_threshold=float(description_threshold),
        ),
    )
except (ValueError, pd.errors.ParserError) as exc:
    st.error(str(exc))
    st.stop()

period_start = min(result.bank["date"].min(), result.gl["date"].min())
period_end = max(result.bank["date"].max(), result.gl["date"].max())
status = "RECONCILED" if result.is_reconciled else "OPEN"
status_colour = "#00E676" if result.is_reconciled else "#FF3B30"

st.markdown('<div class="eyebrow">MONTH-END CASH CONTROL</div>', unsafe_allow_html=True)
st.title("Bank Reconciliation Automation")
st.markdown(
    f'<div class="period">{period_start:%d %b %Y} — {period_end:%d %b %Y}</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="status-line" style="border-color:{status_colour};color:{status_colour}">'
    f'{status} · residual {money(result.residual)}</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="proof-grid">
      <div class="proof-cell"><div class="proof-label">BANK MOVEMENT</div><div class="proof-value">{money(result.bank_balance)}</div></div>
      <div class="proof-cell"><div class="proof-label">PLUS BANK-SIDE ADJUSTMENTS</div><div class="proof-value">{money(result.bank_adjustments)}</div></div>
      <div class="proof-cell"><div class="proof-label">ADJUSTED BANK</div><div class="proof-value signal">{money(result.adjusted_bank_balance)}</div></div>
      <div class="proof-cell"><div class="proof-label">ADJUSTED BOOK</div><div class="proof-value signal">{money(result.adjusted_book_balance)}</div></div>
      <div class="proof-cell"><div class="proof-label">CONTROL DIFFERENCE</div><div class="proof-value signal">{money(result.residual)}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Matched pairs", f"{len(result.matches):,}")
metric_columns[1].metric("Row match rate", f"{result.match_rate:.1%}")
metric_columns[2].metric("Exceptions", f"{len(result.exceptions):,}")
metric_columns[3].metric(
    "Open exposure",
    compact_money(
        float(result.exceptions["exposure"].sum()) if not result.exceptions.empty else 0.0
    ),
)

power_bi_tab, overview_tab, exception_tab, match_tab, source_tab = st.tabs(
    ["Power BI dashboard", "Control summary", "Exceptions", "Matched transactions", "Source data"]
)

with power_bi_tab:
    if POWER_BI_DASHBOARD.exists():
        dashboard_html = POWER_BI_DASHBOARD.read_text(encoding="utf-8")
        components.html(dashboard_html, height=1020, scrolling=True)
        st.download_button(
            "Download standalone HTML dashboard",
            data=dashboard_html,
            file_name="bank_reconciliation_dashboard.html",
            mime="text/html",
        )
    else:
        st.info("Build the HTML dashboard with `python tools/build_dashboard.py`.")

with overview_tab:
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Match methods")
        method_counts = (
            result.matches.groupby("match_method", as_index=False)
            .size()
            .rename(columns={"size": "matched_pairs"})
        )
        st.dataframe(method_counts, hide_index=True, width="stretch")
    with right:
        st.subheader("Exception classes")
        category_counts = (
            result.exceptions.groupby("category", as_index=False)
            .agg(items=("exception_id", "count"), exposure=("exposure", "sum"))
            .sort_values("exposure", ascending=False)
            if not result.exceptions.empty
            else pd.DataFrame(columns=["category", "items", "exposure"])
        )
        st.dataframe(
            category_counts,
            hide_index=True,
            width="stretch",
            column_config={"exposure": st.column_config.NumberColumn(format="$%.2f")},
        )

    workbook = build_excel_report(result)
    st.download_button(
        "Download reconciliation workbook",
        data=workbook,
        file_name="bank_reconciliation_june_2026.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with exception_tab:
    st.subheader("Review queue")
    st.caption("Ranked by absolute financial exposure. Suggested actions require accountant approval.")
    st.dataframe(
        result.exceptions,
        hide_index=True,
        width="stretch",
        column_config={
            "amount": st.column_config.NumberColumn(format="$%.2f"),
            "exposure": st.column_config.NumberColumn(format="$%.2f"),
            "date": st.column_config.DateColumn(format="YYYY-MM-DD"),
        },
    )

with match_tab:
    st.subheader("Matched transaction audit trail")
    st.dataframe(
        result.matches,
        hide_index=True,
        width="stretch",
        column_config={
            "bank_amount": st.column_config.NumberColumn(format="$%.2f"),
            "gl_amount": st.column_config.NumberColumn(format="$%.2f"),
            "amount_variance": st.column_config.NumberColumn(format="$%.2f"),
            "confidence": st.column_config.ProgressColumn(min_value=0, max_value=100),
        },
    )

with source_tab:
    bank_tab, gl_tab = st.tabs(["Bank statement", "GL cash extract"])
    with bank_tab:
        st.dataframe(bank_input, hide_index=True, width="stretch")
    with gl_tab:
        st.dataframe(gl_input, hide_index=True, width="stretch")
