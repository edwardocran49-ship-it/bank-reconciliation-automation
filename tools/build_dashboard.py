"""Build the standalone Power BI-style HTML dashboard from the sample data."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dashboard.html"
sys.path.insert(0, str(ROOT))

from bank_recon import reconcile  # noqa: E402


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    output = frame.copy()
    for column in output.columns:
        if pd.api.types.is_datetime64_any_dtype(output[column]):
            output[column] = output[column].dt.strftime("%Y-%m-%d")
    return output.where(pd.notna(output), None).to_dict(orient="records")


def dashboard_data() -> dict[str, object]:
    bank = pd.read_csv(ROOT / "data" / "raw" / "bank_statement_jun2026.csv")
    gl = pd.read_csv(ROOT / "data" / "raw" / "gl_cash_extract_jun2026.csv")
    result = reconcile(bank, gl)

    daily_bank = result.bank.groupby("date")["amount"].sum()
    daily_gl = result.gl.groupby("date")["amount"].sum()
    daily = pd.DataFrame({"bank": daily_bank, "gl": daily_gl}).fillna(0).sort_index()
    daily["bank"] = daily["bank"].cumsum()
    daily["gl"] = daily["gl"].cumsum()
    daily = daily.reset_index()

    methods = (
        result.matches.groupby("match_method", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )
    categories = (
        result.exceptions.groupby("category", as_index=False)
        .agg(count=("exception_id", "count"), exposure=("exposure", "sum"))
        .sort_values("exposure", ascending=False)
    )

    period_start = min(result.bank["date"].min(), result.gl["date"].min())
    period_end = max(result.bank["date"].max(), result.gl["date"].max())
    bank_exceptions = result.exceptions[
        (result.exceptions["source"] == "GL")
        & (result.exceptions["category"] != "Possible duplicate")
    ]
    deposits = float(bank_exceptions.loc[bank_exceptions["amount"] > 0, "amount"].sum())
    outstanding = float(bank_exceptions.loc[bank_exceptions["amount"] < 0, "amount"].sum())

    return {
        "period": f"{period_start:%d %b %Y} – {period_end:%d %b %Y}",
        "refresh": datetime.now().astimezone().strftime("%d %b %Y, %H:%M"),
        "summary": {
            "status": "Reconciled" if result.is_reconciled else "Open",
            "bankMovement": result.bank_balance,
            "glMovement": result.gl_balance,
            "adjustedBank": result.adjusted_bank_balance,
            "adjustedBook": result.adjusted_book_balance,
            "residual": result.residual,
            "matchedPairs": len(result.matches),
            "exceptions": len(result.exceptions),
            "matchRate": result.match_rate,
            "openExposure": float(result.exceptions["exposure"].sum()),
        },
        "bankBridge": [
            {"label": "Bank movement", "value": result.bank_balance, "kind": "start"},
            {"label": "Deposits in transit", "value": deposits, "kind": "positive"},
            {"label": "Outstanding payments", "value": outstanding, "kind": "negative"},
            {"label": "Adjusted bank", "value": result.adjusted_bank_balance, "kind": "total"},
        ],
        "bookBridge": [
            {"label": "GL movement", "value": result.gl_balance, "kind": "start"},
            {"label": "Bank-only items", "value": result.bank_only_adjustments, "kind": "positive"},
            {"label": "Duplicate reversal", "value": result.duplicate_reversals, "kind": "positive"},
            {"label": "Amount corrections", "value": result.matched_variance, "kind": "negative"},
            {"label": "Adjusted cash book", "value": result.adjusted_book_balance, "kind": "total"},
        ],
        "daily": _records(daily),
        "methods": _records(methods),
        "categories": _records(categories),
        "exceptions": _records(
            result.exceptions.sort_values(["exposure", "date"], ascending=[False, True])[
                [
                    "exception_id", "source", "date", "description", "reference",
                    "amount", "category", "recommended_action", "exposure",
                ]
            ]
        ),
    }


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bank Reconciliation Dashboard</title>
<style>
:root{--ink:#172033;--muted:#687184;--line:#dfe3ea;--surface:#fff;--canvas:#f4f6f9;--navy:#14395b;--blue:#2878bd;--lightblue:#dcecf8;--red:#c83b3b;--amber:#d28a17;--green:#17795b;--shadow:0 8px 24px rgba(20,57,91,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.4 "Helvetica Neue",Arial,sans-serif;font-variant-numeric:tabular-nums}button,select,input{font:inherit}.shell{min-height:100vh}.topbar{height:68px;background:var(--navy);color:#fff;display:flex;align-items:center;padding:0 28px;gap:22px;position:sticky;top:0;z-index:10}.brand{font-size:20px;font-weight:700;letter-spacing:-.02em}.topbar .rule{height:28px;width:1px;background:rgba(255,255,255,.28)}.period{font-size:13px;color:#d9e5ef}.status{margin-left:auto;border:1px solid rgba(255,255,255,.45);padding:7px 11px;font-weight:700}.status::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:#53d5a5;margin-right:7px}.page{max-width:1540px;margin:auto;padding:22px 26px 36px}.toolbar{display:grid;grid-template-columns:1fr auto auto auto;gap:12px;align-items:end;margin-bottom:16px}.title h1{font-size:28px;line-height:1.05;margin:0 0 6px;letter-spacing:-.035em}.title p{margin:0;color:var(--muted)}.control label{display:block;color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}.control select,.control input{height:38px;min-width:180px;border:1px solid var(--line);background:#fff;padding:0 10px;color:var(--ink)}.reset{height:38px;border:1px solid var(--navy);background:#fff;color:var(--navy);font-weight:700;padding:0 16px;cursor:pointer}.reset:hover{background:var(--navy);color:#fff}.grid{display:grid;gap:14px}.kpis{grid-template-columns:repeat(5,minmax(0,1fr));margin-bottom:14px}.card,.panel{background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow)}.kpi{padding:15px 16px 14px;min-height:108px;border-top:3px solid var(--navy)}.kpi .label{color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em}.kpi .value{font-size:27px;font-weight:750;letter-spacing:-.04em;margin-top:9px}.kpi .detail{font-size:12px;color:var(--muted);margin-top:6px}.kpi.good{border-top-color:var(--green)}.kpi.alert{border-top-color:var(--amber)}.bridge{padding:16px 18px 18px;margin-bottom:14px}.panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}.panel-head h2,.panel-head h3{margin:0;letter-spacing:-.02em}.panel-head h2{font-size:18px}.panel-head h3{font-size:15px}.panel-head p{margin:3px 0 0;color:var(--muted);font-size:12px}.residual{background:#e6f4ee;color:var(--green);padding:9px 12px;font-weight:800}.bridge-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.bridge-lane{border:1px solid var(--line);padding:13px}.lane-name{font-size:12px;font-weight:800;color:var(--navy);margin-bottom:11px}.steps{display:flex;align-items:stretch;gap:7px}.step{position:relative;flex:1;min-width:0;background:#f6f8fb;border-left:4px solid #aab4c4;padding:10px 9px}.step.positive{border-left-color:var(--blue)}.step.negative{border-left-color:var(--red)}.step.total{background:var(--navy);color:#fff;border-left-color:var(--navy)}.step:not(:last-child)::after{content:"";position:absolute;right:-8px;top:50%;width:8px;border-top:1px solid #8993a3}.step-label{font-size:10px;min-height:30px;color:var(--muted)}.step.total .step-label{color:#dbe8f3}.step-value{font-size:16px;font-weight:800;white-space:nowrap}.analytics{grid-template-columns:1.1fr 1.4fr 1fr;margin-bottom:14px}.panel{padding:15px 16px;min-width:0}.coverage-wrap{display:flex;align-items:center;gap:20px;min-height:205px}.ring{width:150px;height:150px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--blue) 0 var(--pct),#e7ebf1 var(--pct) 100%);position:relative}.ring::after{content:"";width:104px;height:104px;background:#fff;border-radius:50%;position:absolute}.ring-text{position:relative;z-index:1;text-align:center}.ring-text strong{font-size:27px;display:block}.ring-text span{font-size:11px;color:var(--muted)}.coverage-notes{display:grid;gap:11px}.coverage-notes strong{font-size:18px;display:block}.coverage-notes span{color:var(--muted);font-size:11px}.method-list,.category-list{display:grid;gap:11px}.bar-row{display:grid;grid-template-columns:minmax(100px,1fr) 2fr auto;gap:9px;align-items:center}.bar-label{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar-track{height:10px;background:#edf0f4}.bar-fill{height:100%;background:var(--blue)}.bar-fill.red{background:var(--red)}.bar-value{font-weight:700;font-size:12px;text-align:right}.trend{grid-column:span 1}.trend svg{width:100%;height:205px;overflow:visible}.axis{stroke:#d8dde5;stroke-width:1}.bank-line{fill:none;stroke:var(--blue);stroke-width:2.5}.gl-line{fill:none;stroke:var(--amber);stroke-width:2.5}.chart-label{font-size:10px;fill:#737d8d}.legend{display:flex;gap:16px;color:var(--muted);font-size:11px}.legend i{display:inline-block;width:14px;border-top:3px solid var(--blue);margin-right:5px;vertical-align:middle}.legend i.gl{border-color:var(--amber)}.exceptions{padding:0;overflow:hidden}.exceptions .panel-head{padding:16px 16px 0}.table-wrap{overflow:auto;max-height:410px;border-top:1px solid var(--line)}table{border-collapse:collapse;width:100%;min-width:1050px}th{position:sticky;top:0;background:#edf2f7;color:#536074;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.07em;padding:10px 12px;border-bottom:1px solid var(--line);z-index:2}td{padding:10px 12px;border-bottom:1px solid #edf0f4;vertical-align:top}td.num,th.num{text-align:right}.source-pill{display:inline-block;border:1px solid #b9c2cf;padding:2px 6px;font-size:10px;font-weight:800}.category{font-weight:700}.action{color:var(--muted);max-width:360px}.empty{padding:38px;text-align:center;color:var(--muted)}.meta{display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:11px;margin-top:12px}.selection-summary{color:var(--muted);font-size:12px}.selection-summary strong{color:var(--ink)}
@media(max-width:1450px){.bridge-grid{grid-template-columns:1fr}.bridge-lane+.bridge-lane{margin-top:2px}}
@media(max-width:1100px){.kpis{grid-template-columns:repeat(2,1fr)}.analytics{grid-template-columns:1fr 1fr}.trend{grid-column:span 2}.toolbar{grid-template-columns:1fr 1fr 1fr}.title{grid-column:1/-1}}
@media(max-width:700px){.page{padding:16px}.topbar{padding:0 16px}.topbar .period,.topbar .rule{display:none}.kpis,.analytics,.toolbar{grid-template-columns:1fr}.trend{grid-column:auto}.steps{display:grid;grid-template-columns:1fr 1fr}.step::after{display:none}.bridge-grid{display:block}.bridge-lane+.bridge-lane{margin-top:12px}.meta{display:block}.control select,.control input{width:100%}}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar"><div class="brand">Bank Reconciliation</div><div class="rule"></div><div class="period" id="period"></div><div class="status" id="status"></div></header>
  <main class="page">
    <section class="toolbar">
      <div class="title"><h1>Month-end cash control</h1><p>Bank-to-GL matching, reconciling items and adjustment review</p></div>
      <div class="control"><label for="sourceFilter">Source</label><select id="sourceFilter"><option value="">All sources</option><option value="BANK">Bank</option><option value="GL">General ledger</option></select></div>
      <div class="control"><label for="categoryFilter">Exception category</label><select id="categoryFilter"><option value="">All categories</option></select></div>
      <button class="reset" id="reset">Reset filters</button>
    </section>

    <section class="grid kpis" id="kpis"></section>

    <section class="panel bridge">
      <div class="panel-head"><div><h2>Reconciliation bridge</h2><p>Both sides resolve to the same adjusted cash movement.</p></div><div class="residual" id="residual"></div></div>
      <div class="bridge-grid"><div class="bridge-lane"><div class="lane-name">Bank statement side</div><div class="steps" id="bankBridge"></div></div><div class="bridge-lane"><div class="lane-name">Cash book side</div><div class="steps" id="bookBridge"></div></div></div>
    </section>

    <section class="grid analytics">
      <article class="panel"><div class="panel-head"><div><h3>Match coverage</h3><p>Source rows matched one-to-one</p></div></div><div class="coverage-wrap"><div class="ring" id="ring"><div class="ring-text"><strong id="rate"></strong><span>match rate</span></div></div><div class="coverage-notes"><div><strong id="pairs"></strong><span>matched pairs</span></div><div><strong id="exceptionCount"></strong><span>exceptions in current view</span></div><div><strong id="exposure"></strong><span>open exposure</span></div></div></div></article>
      <article class="panel trend"><div class="panel-head"><div><h3>Cumulative cash movement</h3><p>Bank statement and GL through the reconciliation period</p></div><div class="legend"><span><i></i>Bank</span><span><i class="gl"></i>GL</span></div></div><svg id="trend" viewBox="0 0 620 210" role="img" aria-label="Cumulative bank and general ledger movement"></svg></article>
      <article class="panel"><div class="panel-head"><div><h3>Match methods</h3><p>Deterministic matching sequence</p></div></div><div class="method-list" id="methods"></div></article>
    </section>

    <section class="grid analytics">
      <article class="panel" style="grid-column:span 2"><div class="panel-head"><div><h3>Exception exposure</h3><p>Absolute value by exception category</p></div></div><div class="category-list" id="categories"></div></article>
      <article class="panel"><div class="panel-head"><div><h3>Review focus</h3><p>Largest items in the current filter context</p></div></div><div id="focus"></div></article>
    </section>

    <section class="panel exceptions">
      <div class="panel-head"><div><h2>Exception review queue</h2><p>Prioritized by financial exposure; all suggested actions require accountant approval.</p></div><div class="selection-summary" id="selection"></div></div>
      <div class="table-wrap"><table><thead><tr><th>ID</th><th>Source</th><th>Date</th><th>Description</th><th>Reference</th><th>Category</th><th class="num">Amount</th><th>Recommended action</th></tr></thead><tbody id="exceptionRows"></tbody></table><div class="empty" id="empty" hidden>No exceptions match the selected filters.</div></div>
    </section>
    <div class="meta"><span>Source: synthetic June 2026 bank statement and GL cash extract</span><span id="refresh"></span><span>Net movement basis; opening and closing balances were not provided.</span></div>
  </main>
</div>
<script>
const DATA=__DATA__;
const money=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2}).format(v);
const number=v=>new Intl.NumberFormat('en-US').format(v);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const shortMoney=v=>{const a=Math.abs(v);if(a>=1e6)return money(v/1e6).replace('.00','')+'M';if(a>=1e3)return money(v/1e3).replace('.00','')+'K';return money(v)};

function renderKpis(filtered){const s=DATA.summary;const exposure=filtered.reduce((a,d)=>a+d.exposure,0);const items=[['Adjusted bank',money(s.adjustedBank),'After bank-side reconciling items','good'],['Adjusted cash book',money(s.adjustedBook),'After book-side corrections','good'],['Control difference',money(s.residual),'Bank less adjusted cash book','good'],['Matched pairs',number(s.matchedPairs),(s.matchRate*100).toFixed(1)+'% of source rows',''],['Exception exposure',money(exposure),number(filtered.length)+' items in current view','alert']];document.getElementById('kpis').innerHTML=items.map(d=>`<article class="card kpi ${d[3]}"><div class="label">${d[0]}</div><div class="value">${d[1]}</div><div class="detail">${d[2]}</div></article>`).join('')}
function renderBridge(id,rows){document.getElementById(id).innerHTML=rows.map(r=>`<div class="step ${r.kind}"><div class="step-label">${esc(r.label)}</div><div class="step-value">${money(r.value)}</div></div>`).join('')}
function renderMethods(){const max=Math.max(...DATA.methods.map(d=>d.count));document.getElementById('methods').innerHTML=DATA.methods.map(d=>`<div class="bar-row"><div class="bar-label">${esc(d.match_method)}</div><div class="bar-track"><div class="bar-fill" style="width:${100*d.count/max}%"></div></div><div class="bar-value">${d.count}</div></div>`).join('')}
function renderTrend(){const svg=document.getElementById('trend'),rows=DATA.daily,w=620,h=210,p={l:54,r:16,t:12,b:28};const vals=rows.flatMap(d=>[d.bank,d.gl]),min=Math.min(0,...vals),max=Math.max(...vals),x=i=>p.l+i*(w-p.l-p.r)/Math.max(1,rows.length-1),y=v=>p.t+(max-v)*(h-p.t-p.b)/(max-min||1),path=k=>rows.map((d,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(d[k]).toFixed(1)).join(' ');const ticks=[min,(min+max)/2,max];svg.innerHTML=ticks.map(v=>`<line class="axis" x1="${p.l}" x2="${w-p.r}" y1="${y(v)}" y2="${y(v)}"/><text class="chart-label" x="${p.l-7}" y="${y(v)+3}" text-anchor="end">${shortMoney(v)}</text>`).join('')+`<path class="bank-line" d="${path('bank')}"/><path class="gl-line" d="${path('gl')}"/><text class="chart-label" x="${p.l}" y="${h-6}">${rows[0].date.slice(5)}</text><text class="chart-label" x="${w-p.r}" y="${h-6}" text-anchor="end">${rows.at(-1).date.slice(5)}</text>`}
function filteredRows(){const source=document.getElementById('sourceFilter').value,category=document.getElementById('categoryFilter').value;return DATA.exceptions.filter(d=>(!source||d.source===source)&&(!category||d.category===category))}
function renderCategories(filtered){const groups={};filtered.forEach(d=>{groups[d.category]??={count:0,exposure:0};groups[d.category].count++;groups[d.category].exposure+=d.exposure});const rows=Object.entries(groups).map(([category,v])=>({category,...v})).sort((a,b)=>b.exposure-a.exposure),max=Math.max(1,...rows.map(d=>d.exposure));document.getElementById('categories').innerHTML=rows.length?rows.map(d=>`<div class="bar-row"><div class="bar-label">${esc(d.category)} <span style="color:var(--muted)">(${d.count})</span></div><div class="bar-track"><div class="bar-fill red" style="width:${100*d.exposure/max}%"></div></div><div class="bar-value">${money(d.exposure)}</div></div>`).join(''):'<div class="empty">No exception exposure for this selection.</div>'}
function renderFocus(filtered){const rows=[...filtered].sort((a,b)=>b.exposure-a.exposure).slice(0,4);document.getElementById('focus').innerHTML=rows.length?rows.map((d,i)=>`<div style="display:grid;grid-template-columns:24px 1fr auto;gap:9px;padding:9px 0;border-bottom:1px solid var(--line)"><strong style="color:var(--navy)">${i+1}</strong><div><div style="font-weight:700">${esc(d.reference)}</div><div style="font-size:11px;color:var(--muted)">${esc(d.category)}</div></div><strong>${money(d.exposure)}</strong></div>`).join(''):'<div class="empty">No items to review.</div>'}
function renderTable(filtered){const body=document.getElementById('exceptionRows'),empty=document.getElementById('empty');body.innerHTML=filtered.map(d=>`<tr><td>${esc(d.exception_id)}</td><td><span class="source-pill">${d.source==='BANK'?'BANK':'GL'}</span></td><td>${esc(d.date)}</td><td>${esc(d.description)}</td><td>${esc(d.reference)}</td><td class="category">${esc(d.category)}</td><td class="num">${money(d.amount)}</td><td class="action">${esc(d.recommended_action)}</td></tr>`).join('');empty.hidden=filtered.length>0;document.getElementById('selection').innerHTML=`<strong>${filtered.length}</strong> exceptions · <strong>${money(filtered.reduce((a,d)=>a+d.exposure,0))}</strong> exposure`}
function update(){const rows=filteredRows();renderKpis(rows);renderCategories(rows);renderFocus(rows);renderTable(rows);document.getElementById('exceptionCount').textContent=number(rows.length);document.getElementById('exposure').textContent=money(rows.reduce((a,d)=>a+d.exposure,0))}

document.getElementById('period').textContent=DATA.period;document.getElementById('status').textContent=DATA.summary.status;document.getElementById('refresh').textContent='Dashboard generated '+DATA.refresh;document.getElementById('residual').textContent='Difference '+money(DATA.summary.residual);document.getElementById('rate').textContent=(DATA.summary.matchRate*100).toFixed(1)+'%';document.getElementById('ring').style.setProperty('--pct',(DATA.summary.matchRate*100)+'%');document.getElementById('pairs').textContent=number(DATA.summary.matchedPairs);renderBridge('bankBridge',DATA.bankBridge);renderBridge('bookBridge',DATA.bookBridge);renderMethods();renderTrend();
const categories=[...new Set(DATA.exceptions.map(d=>d.category))].sort();document.getElementById('categoryFilter').insertAdjacentHTML('beforeend',categories.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join(''));document.getElementById('sourceFilter').addEventListener('change',update);document.getElementById('categoryFilter').addEventListener('change',update);document.getElementById('reset').addEventListener('click',()=>{document.getElementById('sourceFilter').value='';document.getElementById('categoryFilter').value='';update()});update();
</script>
</body>
</html>'''


def main() -> None:
    payload = json.dumps(dashboard_data(), separators=(",", ":"), ensure_ascii=False)
    OUTPUT.write_text(HTML.replace("__DATA__", payload), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
