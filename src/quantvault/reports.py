"""Bloomberg-style research reports and HTML chart rendering."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from quantvault.ledger import Ledger


def _load_json_artifact(ledger: Ledger, experiment_id: str, name: str) -> Any:
    exp = ledger.require(experiment_id)
    for art in ledger.list_artifacts(exp.id):
        if art["name"] == name:
            return json.loads(Path(art["path"]).read_text(encoding="utf-8"))
    return None


def load_analysis_artifact(ledger: Ledger, experiment_id: str) -> dict[str, Any] | None:
    return _load_json_artifact(ledger, experiment_id, "performance_report.json")


def research_report(ledger: Ledger, experiment_id: str) -> dict[str, Any]:
    exp = ledger.require(experiment_id)
    return {
        "experiment": exp.to_dict(),
        "repro": ledger.get_repro(exp.id),
        "artifacts": ledger.list_artifacts(exp.id),
        "analysis": load_analysis_artifact(ledger, exp.id),
        "monte_carlo": _load_json_artifact(ledger, exp.id, "monte_carlo.json"),
        "walk_forward": _load_json_artifact(ledger, exp.id, "walk_forward.json"),
        "robustness": _load_json_artifact(ledger, exp.id, "robustness.json"),
        "validation": _load_json_artifact(ledger, exp.id, "validation.json"),
        "overfitting": _load_json_artifact(ledger, exp.id, "overfitting.json"),
        "custom_charts": _load_json_artifact(ledger, exp.id, "custom_charts.json"),
        "lineage": [e.to_dict() for e in ledger.lineage(exp.id)],
        "children": [e.to_dict() for e in ledger.children(exp.id)],
    }


def _bb_css() -> str:
    return """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root {
  --bg: #0b0e11;
  --panel: #12161c;
  --panel-2: #171c24;
  --line: #2a3340;
  --text: #d7dde5;
  --muted: #8b95a5;
  --amber: #ff9f1a;
  --amber-dim: #c47a12;
  --green: #18c96a;
  --red: #ff4d4f;
  --blue: #3aa0ff;
  --cyan: #2ad4c5;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
  font-family: "IBM Plex Sans", system-ui, sans-serif; }
a { color: var(--amber); text-decoration: none; }
a:hover { color: #ffc266; }
.topbar {
  display: flex; align-items: center; gap: 1rem; padding: .55rem 1rem;
  border-bottom: 1px solid var(--line); background: #080a0d;
  position: sticky; top: 0; z-index: 20;
}
.brand { font-family: "IBM Plex Mono", monospace; font-weight: 600; color: var(--amber);
  letter-spacing: .04em; font-size: .95rem; }
.brand span { color: var(--muted); font-weight: 400; }
.pill { font-family: "IBM Plex Mono", monospace; font-size: .72rem; color: var(--muted);
  border: 1px solid var(--line); padding: .15rem .45rem; }
.wrap { padding: .7rem .85rem 1.5rem; max-width: 1480px; margin: 0 auto; }
h1 { margin: 0; font-size: 1.25rem; font-weight: 600; }
h2 { margin: 0 0 .65rem; font-size: .78rem; font-weight: 600; color: var(--amber);
  text-transform: uppercase; letter-spacing: .08em; font-family: "IBM Plex Mono", monospace; }
.sub { color: var(--muted); font-size: .85rem; margin-top: .2rem; }
.grid { display: grid; gap: .65rem; }
.grid-kpi { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.grid-2 { grid-template-columns: 1.45fr 1fr; }
.grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-main { grid-template-columns: 1.45fr 1fr; }
@media (max-width: 900px) {
  .grid-kpi { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .grid-2, .grid-3, .grid-main { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .grid-kpi { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.panel { background: var(--panel); border: 1px solid var(--line); padding: .65rem .7rem; }
.kpi { background: var(--panel-2); border: 1px solid var(--line); padding: .45rem .55rem; min-height: 58px; }
.kpi .label { font-family: "IBM Plex Mono", monospace; font-size: .62rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: .06em; }
.kpi .value { font-family: "IBM Plex Mono", monospace; font-size: 1.02rem; font-weight: 600;
  margin-top: .15rem; color: var(--text); }
.kpi .value.pos { color: var(--green); }
.kpi .value.neg { color: var(--red); }
.kpi .value.amber { color: var(--amber); }
.table-wrap { overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
th { text-align: left; color: var(--muted); font-family: "IBM Plex Mono", monospace;
  font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
  border-bottom: 1px solid var(--line); padding: .4rem .35rem; font-weight: 500; }
td { border-bottom: 1px solid #1c2430; padding: .42rem .35rem; font-family: "IBM Plex Mono", monospace;
  font-size: .78rem; white-space: nowrap; }
tr:hover td { background: #1a222d; }
.badge { display: inline-block; border: 1px solid var(--line); color: var(--muted);
  padding: .05rem .35rem; font-size: .68rem; margin-right: .2rem; }
.badge.ok { color: var(--green); border-color: #1f5a3a; }
.badge.warn { color: var(--amber); border-color: #5a4010; }
.badge.bad { color: var(--red); border-color: #5a2020; }
.chart-box { position: relative; height: 240px; }
.chart-box.sm { height: 180px; }
.mono { font-family: "IBM Plex Mono", monospace; }
.empty { color: var(--muted); font-size: .85rem; padding: .5rem 0; }
.kv { display: grid; grid-template-columns: 120px 1fr; gap: .25rem .75rem; font-size: .8rem; }
.kv .k { color: var(--muted); font-family: "IBM Plex Mono", monospace; font-size: .72rem; }
.kv .v { font-family: "IBM Plex Mono", monospace; word-break: break-all; }
.footer { margin-top: 1rem; color: var(--muted); font-size: .72rem; font-family: "IBM Plex Mono", monospace; }
"""


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def _cls(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "pos"
    if v < 0:
        return "neg"
    return ""


def _kpi(label: str, value: Any, *, digits: int = 4, force_class: str = "") -> str:
    cls = force_class or _cls(value)
    return (
        f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
        f'<div class="value {cls}">{html.escape(_fmt(value, digits))}</div></div>'
    )


def render_experiment_html(ledger: Ledger, experiment_id: str) -> str:
    report = research_report(ledger, experiment_id)
    exp = report["experiment"]
    analysis = report.get("analysis") or {}
    mc = report.get("monte_carlo") or {}
    wf = report.get("walk_forward") or {}
    rob = report.get("robustness") or {}
    validation = report.get("validation") or {}
    overfitting = report.get("overfitting") or {}
    custom_charts = report.get("custom_charts") or []
    if isinstance(custom_charts, dict):
        custom_charts = [custom_charts]
    repro = report.get("repro") or {}
    series = analysis.get("series") or {}
    risk = analysis.get("risk_adjusted") or {}
    equity = analysis.get("equity_curve") or {}
    dd = analysis.get("drawdown") or {}
    trades = analysis.get("trades") or {}
    costs = analysis.get("transaction_costs") or {}
    bench = analysis.get("benchmark") or {}
    srsi = analysis.get("srsi") or {}
    edge = mc.get("edge") or {}

    metrics = exp.get("metrics") or {}
    params = exp.get("params") or {}
    tags = exp.get("tags") or []

    payload = {
        "equity": series.get("equity") or [],
        "drawdown": series.get("drawdown") or dd.get("path") or [],
        "returns": series.get("returns") or [],
        "mc_fan": mc.get("fan") or {},
        "mc_dist": mc.get("distribution") or {},
        "wf": wf.get("windows") or [],
        "rolling_sharpe": srsi.get("rolling_sharpes") or [],
        "custom_charts": custom_charts,
    }

    tag_html = " ".join(f'<span class="badge">{html.escape(t)}</span>' for t in tags)
    param_rows = "".join(
        f'<div class="k">{html.escape(str(k))}</div><div class="v">{html.escape(json.dumps(v))}</div>'
        for k, v in sorted(params.items())
    ) or '<div class="empty">No parameters</div>'

    lineage_rows = "".join(
        "<tr>"
        f"<td><a href='/experiment/{html.escape(e['id'])}'>{html.escape(e['id'][:10])}</a></td>"
        f"<td>{html.escape(e['name'])}</td>"
        f"<td>{html.escape(e.get('strategy') or '')}</td>"
        f"<td class='{_cls((e.get('metrics') or {}).get('sharpe'))}'>{html.escape(_fmt((e.get('metrics') or {}).get('sharpe')))}</td>"
        "</tr>"
        for e in report.get("lineage") or []
    )

    child_rows = "".join(
        "<tr>"
        f"<td><a href='/experiment/{html.escape(e['id'])}'>{html.escape(e['id'][:10])}</a></td>"
        f"<td>{html.escape(e['name'])}</td>"
        f"<td class='{_cls((e.get('metrics') or {}).get('sharpe'))}'>{html.escape(_fmt((e.get('metrics') or {}).get('sharpe')))}</td>"
        "</tr>"
        for e in report.get("children") or []
    ) or "<tr><td colspan='3' class='empty'>No child experiments</td></tr>"

    art_rows = "".join(
        "<tr>"
        f"<td>{html.escape(a['name'])}</td>"
        f"<td>{html.escape(a.get('kind') or '')}</td>"
        f"<td>{html.escape((a.get('fingerprint') or '')[:12])}</td>"
        "</tr>"
        for a in report.get("artifacts") or []
    ) or "<tr><td colspan='3' class='empty'>No artifacts</td></tr>"

    def _flag_rows(items: list[dict[str, Any]] | None) -> str:
        rows = []
        for item in items or []:
            msg = item.get("message") or item.get("check") or json.dumps(item, default=str)
            code = item.get("code") or item.get("severity") or item.get("id") or ""
            rows.append(
                "<tr>"
                f"<td class='amber'>{html.escape(str(code))}</td>"
                f"<td>{html.escape(str(msg))}</td>"
                "</tr>"
            )
        return "".join(rows) or "<tr><td colspan='2' class='empty'>No flags</td></tr>"

    quality = validation.get("quality_warnings") or []
    integrity = validation.get("integrity") or []
    data_q = validation.get("data_quality") or []
    lookahead = validation.get("lookahead") or []
    survivorship = validation.get("survivorship") or []
    leakage = validation.get("leakage") or []
    repro_v = validation.get("reproducibility") or {}
    flag_count = sum(len(x) for x in (quality, integrity, data_q, lookahead, survivorship, leakage))
    validation_panel = f"""
    <div class="panel table-wrap" style="margin-bottom:.75rem;">
      <h2>Research Quality & Validation</h2>
      <div class="sub mono" style="margin-bottom:.55rem;">
        {flag_count} flags · repro complete={html.escape(str(repro_v.get('complete', '—')))} ·
        missing={html.escape(', '.join(repro_v.get('missing') or []) or '—')}
      </div>
      <div class="grid grid-3">
        <div>
          <div class="sub" style="margin-bottom:.3rem;">Quality warnings</div>
          <table><thead><tr><th>Code</th><th>Message</th></tr></thead><tbody>{_flag_rows(quality)}</tbody></table>
        </div>
        <div>
          <div class="sub" style="margin-bottom:.3rem;">Integrity / data</div>
          <table><thead><tr><th>Code</th><th>Message</th></tr></thead>
          <tbody>{_flag_rows(integrity + data_q)}</tbody></table>
        </div>
        <div>
          <div class="sub" style="margin-bottom:.3rem;">Bias heuristics</div>
          <table><thead><tr><th>Code</th><th>Message</th></tr></thead>
          <tbody>{_flag_rows(lookahead + survivorship + leakage)}</tbody></table>
        </div>
      </div>
    </div>
    """ if validation else """
    <div class="panel" style="margin-bottom:.75rem;">
      <h2>Research Quality & Validation</h2>
      <div class="empty">Run <span class="mono">quant-vault validate &lt;id&gt;</span> to populate</div>
    </div>
    """

    title = html.escape(f"{exp['name']}")
    exp_id = html.escape(exp["id"])
    strategy = html.escape(exp.get("strategy") or "n/a")
    payload_json = json.dumps(payload)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>QL · {title}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>{_bb_css()}</style>
</head>
<body>
  <div class="topbar">
    <div class="brand"><a href="/">QuantVault</a> <span>TERMINAL</span></div>
    <span class="pill">EXP {exp_id}</span>
    <span class="pill">{strategy}</span>
    <span class="pill">{html.escape(exp.get("status") or "")}</span>
    <div style="margin-left:auto" class="pill"><a href="/strategy/{strategy}">STRATEGY BOOK</a></div>
  </div>
  <div class="wrap">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin-bottom:.85rem;">
      <div>
        <h1>{title}</h1>
        <div class="sub mono">{exp_id} · parent {html.escape(str(exp.get('parent_id') or '—'))}</div>
        <div style="margin-top:.35rem">{tag_html}</div>
      </div>
      <div class="sub mono">{html.escape(exp.get('created_at') or '')}</div>
    </div>

    <div class="grid grid-kpi" style="margin-bottom:.75rem;">
      {_kpi("Sharpe", risk.get("sharpe", metrics.get("sharpe")))}
      {_kpi("Sortino", risk.get("sortino", metrics.get("sortino")))}
      {_kpi("Calmar", risk.get("calmar", metrics.get("calmar")))}
      {_kpi("Total Ret", equity.get("total_return", metrics.get("total_return")))}
      {_kpi("Max DD", dd.get("max_drawdown", metrics.get("max_drawdown")))}
      {_kpi("SRSI", srsi.get("srsi", metrics.get("srsi")), force_class="amber")}
    </div>

    <div class="grid grid-main" style="margin-bottom:.75rem;">
      <div class="panel">
        <h2>Equity & Drawdown</h2>
        <div class="chart-box"><canvas id="equityChart"></canvas></div>
      </div>
      <div class="panel">
        <h2>Monte Carlo</h2>
        <div class="grid" style="grid-template-columns:1fr 1fr; gap:.5rem; margin-bottom:.6rem;">
          {_kpi("P(final>0)", edge.get("prob_positive"), digits=3)}
          {_kpi("Median final", edge.get("median_final"))}
          {_kpi("Tail p05", edge.get("tail_p05"))}
          {_kpi("Mean final", edge.get("mean_final"))}
        </div>
        <div class="chart-box sm"><canvas id="mcFanChart"></canvas></div>
      </div>
    </div>

    <div class="grid grid-3" style="margin-bottom:.75rem;">
      <div class="panel">
        <h2>Return Distribution</h2>
        <div class="chart-box sm"><canvas id="mcDistChart"></canvas></div>
      </div>
      <div class="panel">
        <h2>Rolling Sharpe (SRSI)</h2>
        <div class="chart-box sm"><canvas id="srsiChart"></canvas></div>
      </div>
      <div class="panel">
        <h2>Walk-Forward</h2>
        <div class="chart-box sm"><canvas id="wfChart"></canvas></div>
        <div class="sub mono" style="margin-top:.4rem;">
          test mean {_fmt(wf.get('test_mean'))} · gap {_fmt(wf.get('gap_mean'))}
        </div>
      </div>
    </div>

    <div class="grid grid-3" style="margin-bottom:.75rem;">
      <div class="panel">
        <h2>Trade Analytics</h2>
        <div class="kv">
          <div class="k">trades</div><div class="v">{html.escape(_fmt(trades.get('n'), 0))}</div>
          <div class="k">win rate</div><div class="v">{html.escape(_fmt(trades.get('win_rate')))}</div>
          <div class="k">profit factor</div><div class="v">{html.escape(_fmt(trades.get('profit_factor')))}</div>
          <div class="k">avg pnl</div><div class="v">{html.escape(_fmt(trades.get('avg_pnl')))}</div>
          <div class="k">best / worst</div><div class="v">{html.escape(_fmt(trades.get('best')))} / {html.escape(_fmt(trades.get('worst')))}</div>
        </div>
      </div>
      <div class="panel">
        <h2>Costs & Benchmark</h2>
        <div class="kv">
          <div class="k">cost drag</div><div class="v">{html.escape(_fmt(costs.get('pnl_drag')))}</div>
          <div class="k">total cost</div><div class="v">{html.escape(_fmt(costs.get('total_cost')))}</div>
          <div class="k">alpha</div><div class="v">{html.escape(_fmt(bench.get('alpha')))}</div>
          <div class="k">beta</div><div class="v">{html.escape(_fmt(bench.get('beta')))}</div>
          <div class="k">info ratio</div><div class="v">{html.escape(_fmt(bench.get('information_ratio')))}</div>
        </div>
      </div>
      <div class="panel">
        <h2>Parameters</h2>
        <div class="kv">{param_rows}</div>
      </div>
    </div>

    <div class="grid grid-2" style="margin-bottom:.75rem;">
      <div class="panel">
        <h2>Reproducibility</h2>
        <div class="kv">
          <div class="k">seed</div><div class="v">{html.escape(str(repro.get('seed') if repro else '—'))}</div>
          <div class="k">dataset</div><div class="v">{html.escape(str(repro.get('dataset_id') or repro.get('dataset_fingerprint') or '—'))}</div>
          <div class="k">config fp</div><div class="v">{html.escape(str((repro.get('config_fingerprint') or '—'))[:24])}</div>
          <div class="k">repro fp</div><div class="v">{html.escape(str((repro.get('repro_fingerprint') or '—'))[:24])}</div>
          <div class="k">python</div><div class="v">{html.escape(str(((repro.get('environment') or {}).get('python_version') or '—')))}</div>
          <div class="k">platform</div><div class="v">{html.escape(str(((repro.get('environment') or {}).get('platform') or '—')))}</div>
        </div>
      </div>
      <div class="panel">
        <h2>Robustness / Notes</h2>
        <div class="kv">
          <div class="k">rob score</div><div class="v">{html.escape(_fmt(rob.get('robustness_score')))}</div>
          <div class="k">metric cv</div><div class="v">{html.escape(_fmt(rob.get('cv')))}</div>
          <div class="k">IS sharpe</div><div class="v">{html.escape(_fmt(metrics.get('in_sample_sharpe')))}</div>
          <div class="k">OOS sharpe</div><div class="v">{html.escape(_fmt(metrics.get('oos_sharpe')))}</div>
          <div class="k">overfit gap</div><div class="v">{html.escape(_fmt(overfitting.get('relative_gap', metrics.get('overfit_relative_gap'))))}</div>
          <div class="k">overfit flag</div><div class="v">{html.escape(str(overfitting.get('overfit_flag', '—')))}</div>
        </div>
        <div class="sub" style="margin-top:.6rem;">{html.escape(exp.get('notes') or 'No notes')}</div>
      </div>
    </div>

    {validation_panel}

    <div class="panel" style="margin-bottom:.75rem;">
      <h2>Custom Charts</h2>
      <div id="customCharts"></div>
      <div class="empty" id="customChartsEmpty" style="display:none;">No custom charts - store via <span class="mono">quant-vault chart</span></div>
    </div>

    <div class="grid grid-3">
      <div class="panel table-wrap">
        <h2>Lineage</h2>
        <table><thead><tr><th>ID</th><th>Name</th><th>Strategy</th><th>Sharpe</th></tr></thead>
        <tbody>{lineage_rows}</tbody></table>
      </div>
      <div class="panel table-wrap">
        <h2>Children</h2>
        <table><thead><tr><th>ID</th><th>Name</th><th>Sharpe</th></tr></thead>
        <tbody>{child_rows}</tbody></table>
      </div>
      <div class="panel table-wrap">
        <h2>Artifacts</h2>
        <table><thead><tr><th>Name</th><th>Kind</th><th>Hash</th></tr></thead>
        <tbody>{art_rows}</tbody></table>
      </div>
    </div>
    <div class="footer">LOCAL VISUALIZATION LAYER · SAME CORE AS PYTHON API / CLI</div>
  </div>
<script>
const D = {payload_json};
const tick = {{ color:'#8b95a5', font:{{ family:'IBM Plex Mono', size:10 }} }};
const grid = {{ color:'#1c2430' }};
const common = {{
  responsive:true, maintainAspectRatio:false,
  plugins:{{ legend:{{ labels:{{ color:'#8b95a5', boxWidth:10, font:{{ family:'IBM Plex Mono', size:10 }} }} }} }},
  scales:{{
    x:{{ ticks:tick, grid }},
    y:{{ ticks:tick, grid }}
  }}
}};

(function(){{
  const eq = D.equity || [];
  const dd = D.drawdown || [];
  new Chart(document.getElementById('equityChart'), {{
    type:'line',
    data:{{
      labels: eq.map((_,i)=>i),
      datasets:[
        {{ label:'Equity', data:eq, borderColor:'#ff9f1a', backgroundColor:'rgba(255,159,26,.08)', fill:true, pointRadius:0, borderWidth:1.5, yAxisID:'y' }},
        {{ label:'Drawdown', data:dd, borderColor:'#ff4d4f', pointRadius:0, borderWidth:1, yAxisID:'y1' }}
      ]
    }},
    options:{{
      ...common,
      scales:{{
        x:{{ ticks:tick, grid }},
        y:{{ position:'left', ticks:tick, grid }},
        y1:{{ position:'right', ticks:{{ ...tick, callback:v => (v*100).toFixed(1)+'%' }}, grid:{{ drawOnChartArea:false }} }}
      }}
    }}
  }});
}})();

(function(){{
  const fan = D.mc_fan || {{}};
  if (!fan.p50 || !fan.p50.length) {{
    document.getElementById('mcFanChart').parentElement.innerHTML = '<div class="empty">Run montecarlo to populate fan chart</div>';
    return;
  }}
  const labels = fan.p50.map((_,i)=>i);
  new Chart(document.getElementById('mcFanChart'), {{
    type:'line',
    data:{{
      labels,
      datasets:[
        {{ label:'p95', data:fan.p95, borderColor:'rgba(24,201,106,.35)', pointRadius:0, borderWidth:1, fill:false }},
        {{ label:'p75', data:fan.p75, borderColor:'rgba(24,201,106,.55)', pointRadius:0, borderWidth:1, fill:'-1', backgroundColor:'rgba(24,201,106,.08)' }},
        {{ label:'p50', data:fan.p50, borderColor:'#ff9f1a', pointRadius:0, borderWidth:2, fill:false }},
        {{ label:'p25', data:fan.p25, borderColor:'rgba(255,77,79,.55)', pointRadius:0, borderWidth:1, fill:false }},
        {{ label:'p05', data:fan.p05, borderColor:'rgba(255,77,79,.35)', pointRadius:0, borderWidth:1, fill:'-1', backgroundColor:'rgba(255,77,79,.08)' }}
      ]
    }},
    options:{{
      ...common,
      plugins:{{ legend:{{ display:true, labels:{{ color:'#8b95a5', boxWidth:10, font:{{ family:'IBM Plex Mono', size:9 }} }} }} }},
      scales:{{
        x:{{ ticks:tick, grid }},
        y:{{ ticks:{{ ...tick, callback:v => (v*100).toFixed(0)+'%' }}, grid }}
      }}
    }}
  }});
}})();

(function(){{
  const dist = D.mc_dist || {{}};
  if (!dist.bins || !dist.bins.length) {{
    document.getElementById('mcDistChart').parentElement.innerHTML = '<div class="empty">No distribution</div>';
    return;
  }}
  new Chart(document.getElementById('mcDistChart'), {{
    type:'bar',
    data:{{
      labels: dist.bins.map(v => (v*100).toFixed(1)+'%'),
      datasets:[{{ data:dist.counts, backgroundColor: dist.bins.map(v => v>=0 ? 'rgba(24,201,106,.7)' : 'rgba(255,77,79,.7)'), borderWidth:0 }}]
    }},
    options:{{ ...common, plugins:{{ legend:{{ display:false }} }} }}
  }});
}})();

(function(){{
  const rs = D.rolling_sharpe || [];
  if (!rs.length) {{
    document.getElementById('srsiChart').parentElement.innerHTML = '<div class="empty">No rolling Sharpe</div>';
    return;
  }}
  new Chart(document.getElementById('srsiChart'), {{
    type:'line',
    data:{{ labels: rs.map((_,i)=>i), datasets:[{{ data:rs, borderColor:'#3aa0ff', pointRadius:0, borderWidth:1.5, fill:false }}] }},
    options:{{ ...common, plugins:{{ legend:{{ display:false }} }} }}
  }});
}})();

(function(){{
  const windows = D.wf || [];
  if (!windows.length) {{
    document.getElementById('wfChart').parentElement.innerHTML = '<div class="empty">No walk-forward windows</div>';
    return;
  }}
  new Chart(document.getElementById('wfChart'), {{
    type:'bar',
    data:{{
      labels: windows.map((w,i)=> w.start || ('W'+(i+1))),
      datasets:[
        {{ label:'Train', data: windows.map(w=>w.train_metric), backgroundColor:'#3aa0ff' }},
        {{ label:'Test', data: windows.map(w=>w.test_metric), backgroundColor:'#ff9f1a' }}
      ]
    }},
    options: common
  }});
}})();

(function(){{
  const charts = D.custom_charts || [];
  const host = document.getElementById('customCharts');
  const empty = document.getElementById('customChartsEmpty');
  if (!charts.length) {{
    empty.style.display = 'block';
    return;
  }}
  charts.forEach((spec, idx) => {{
    const wrap = document.createElement('div');
    wrap.style.marginBottom = '.75rem';
    const title = document.createElement('div');
    title.className = 'sub mono';
    title.style.marginBottom = '.35rem';
    title.textContent = spec.title || spec.name || ('chart-' + (idx+1));
    const box = document.createElement('div');
    box.className = 'chart-box sm';
    const canvas = document.createElement('canvas');
    box.appendChild(canvas);
    wrap.appendChild(title);
    wrap.appendChild(box);
    host.appendChild(wrap);
    new Chart(canvas, {{
      type: spec.type || 'line',
      data: {{
        labels: spec.labels || [],
        datasets: (spec.datasets || []).map((ds, i) => ({{
          label: ds.label || ('series-' + (i+1)),
          data: ds.data || [],
          borderColor: ds.borderColor || ['#ff9f1a','#3aa0ff','#18c96a','#ff4d4f'][i % 4],
          backgroundColor: ds.backgroundColor || 'rgba(255,159,26,.15)',
          pointRadius: ds.pointRadius ?? 0,
          borderWidth: ds.borderWidth ?? 1.5,
          fill: ds.fill ?? false,
        }}))
      }},
      options: common
    }});
  }});
}})();
</script>
</body>
</html>
"""


def render_ledger_html(ledger: Ledger) -> str:
    experiments = [e.to_dict() for e in ledger.list()]
    strategies: dict[str, list[dict[str, Any]]] = {}
    for exp in experiments:
        strategies.setdefault(exp.get("strategy") or "(none)", []).append(exp)

    portfolios = ledger.list_portfolios()
    live_runs = ledger.list_live()

    rows = []
    labels = []
    sharpes = []
    for exp in experiments:
        m = exp.get("metrics") or {}
        sharpe = m.get("sharpe")
        labels.append(exp["id"][:8])
        sharpes.append(sharpe)
        sharpe_cls = _cls(sharpe)
        tags = " ".join(f'<span class="badge">{html.escape(t)}</span>' for t in (exp.get("tags") or [])[:3])
        rows.append(
            "<tr>"
            f"<td><a href='/experiment/{html.escape(exp['id'])}'>{html.escape(exp['id'][:10])}</a></td>"
            f"<td><a href='/experiment/{html.escape(exp['id'])}'>{html.escape(exp['name'])}</a></td>"
            f"<td><a href='/strategy/{html.escape(exp.get('strategy') or '')}'>{html.escape(exp.get('strategy') or '—')}</a></td>"
            f"<td>{html.escape(exp.get('status') or '')}</td>"
            f"<td class='{sharpe_cls}'>{html.escape(_fmt(sharpe))}</td>"
            f"<td class='{_cls(m.get('max_drawdown'))}'>{html.escape(_fmt(m.get('max_drawdown')))}</td>"
            f"<td class='{_cls(m.get('total_return'))}'>{html.escape(_fmt(m.get('total_return')))}</td>"
            f"<td>{html.escape(_fmt(m.get('srsi')))}</td>"
            f"<td>{tags}</td>"
            "</tr>"
        )

    strat_cards = []
    for name, items in sorted(strategies.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        vals = [float((e.get("metrics") or {}).get("sharpe")) for e in items if (e.get("metrics") or {}).get("sharpe") is not None]
        avg = sum(vals) / len(vals) if vals else None
        strat_cards.append(
            f'<a class="panel" href="/strategy/{html.escape(name)}" style="display:block;">'
            f'<h2>{html.escape(name)}</h2>'
            f'<div class="kpi"><div class="label">runs</div><div class="value amber">{len(items)}</div></div>'
            f'<div class="sub mono" style="margin-top:.4rem;">avg sharpe {html.escape(_fmt(avg))}</div>'
            f'</a>'
        )

    portfolio_rows = "".join(
        "<tr>"
        f"<td class='mono'>{html.escape(p['id'][:10])}</td>"
        f"<td>{html.escape(p['name'])}</td>"
        f"<td>{html.escape(', '.join(f'{k}={_fmt(v)}' for k, v in (p.get('weights') or {}).items()))}</td>"
        f"<td class='mono'>{html.escape(str(len(p.get('experiment_ids') or [])))}</td>"
        f"<td class='mono'>{html.escape(p.get('created_at') or '')}</td>"
        "</tr>"
        for p in portfolios
    ) or "<tr><td colspan='5' class='empty'>No portfolios yet</td></tr>"

    live_rows = "".join(
        "<tr>"
        f"<td class='mono'>{html.escape(r['id'][:10])}</td>"
        f"<td>{html.escape(r['name'])}</td>"
        f"<td><span class='badge'>{html.escape(r.get('kind') or '')}</span></td>"
        f"<td><a href='/experiment/{html.escape(r['backtest_id'])}'>{html.escape((r.get('backtest_id') or '—')[:10])}</a></td>"
        f"<td class='{_cls(((r.get('metrics') or {}).get('comparison') or {}).get('live_mean'))}'>"
        f"{html.escape(_fmt(((r.get('metrics') or {}).get('comparison') or {}).get('live_mean')))}</td>"
        f"<td class='mono'>{html.escape(r.get('created_at') or '')}</td>"
        "</tr>"
        for r in live_runs
    ) or "<tr><td colspan='6' class='empty'>No paper/live runs yet</td></tr>"

    chart = json.dumps({"labels": labels, "sharpes": sharpes})
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>QV · Monitor</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>{_bb_css()}</style>
</head>
<body>
  <div class="topbar">
    <div class="brand">QuantVault <span>TERMINAL</span></div>
    <span class="pill">{len(experiments)} EXPERIMENTS</span>
    <span class="pill">{len(strategies)} STRATEGIES</span>
    <span class="pill">{len(portfolios)} PORTFOLIOS</span>
    <span class="pill">{len(live_runs)} LIVE/PAPER</span>
    <span class="pill">LOCAL</span>
  </div>
  <div class="wrap">
    <div class="grid grid-main" style="margin-bottom:.75rem;">
      <div class="panel">
        <h2>Sharpe Monitor</h2>
        <div class="chart-box"><canvas id="sharpe"></canvas></div>
      </div>
      <div class="panel">
        <h2>Strategy Books</h2>
        <div class="grid" style="gap:.5rem;">{"".join(strat_cards) or '<div class="empty">No strategies</div>'}</div>
      </div>
    </div>
    <div class="panel table-wrap" style="margin-bottom:.75rem;">
      <h2>Experiment Blotter</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Name</th><th>Strategy</th><th>Status</th>
            <th>Sharpe</th><th>Max DD</th><th>Return</th><th>SRSI</th><th>Tags</th>
          </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
    <div class="grid grid-2" style="margin-bottom:.75rem;">
      <div class="panel table-wrap">
        <h2>Portfolios</h2>
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Weights</th><th>Legs</th><th>Created</th></tr></thead>
          <tbody>{portfolio_rows}</tbody>
        </table>
      </div>
      <div class="panel table-wrap">
        <h2>Paper / Live</h2>
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Kind</th><th>Backtest</th><th>Live mean</th><th>Created</th></tr></thead>
          <tbody>{live_rows}</tbody>
        </table>
      </div>
    </div>
    <div class="footer">CLICK ANY EXPERIMENT · VALIDATION · MONTE CARLO · WF · REPRO · PORTFOLIO · PAPER/LIVE</div>
  </div>
<script>
const data = {chart};
new Chart(document.getElementById('sharpe'), {{
  type: 'bar',
  data: {{
    labels: data.labels,
    datasets: [{{
      data: data.sharpes,
      backgroundColor: data.sharpes.map(v => (v||0) >= 0 ? '#18c96a' : '#ff4d4f')
    }}]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ display:false }} }},
    scales:{{
      x:{{ ticks:{{ color:'#8b95a5', font:{{ family:'IBM Plex Mono', size:10 }} }}, grid:{{ color:'#1c2430' }} }},
      y:{{ ticks:{{ color:'#8b95a5', font:{{ family:'IBM Plex Mono', size:10 }} }}, grid:{{ color:'#1c2430' }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""


def render_strategy_html(ledger: Ledger, strategy: str) -> str:
    experiments = [e.to_dict() for e in ledger.list(strategy=strategy)]
    if strategy == "(none)":
        experiments = [e.to_dict() for e in ledger.list() if not e.strategy]

    sharpes = [(e.get("metrics") or {}).get("sharpe") for e in experiments]
    returns = [(e.get("metrics") or {}).get("total_return") for e in experiments]
    dds = [(e.get("metrics") or {}).get("max_drawdown") for e in experiments]
    valid_s = [float(x) for x in sharpes if x is not None]
    avg_sharpe = sum(valid_s) / len(valid_s) if valid_s else None
    best = max(experiments, key=lambda e: float((e.get("metrics") or {}).get("sharpe") or -1e9), default=None)

    rows = []
    for exp in experiments:
        m = exp.get("metrics") or {}
        rows.append(
            "<tr>"
            f"<td><a href='/experiment/{html.escape(exp['id'])}'>{html.escape(exp['id'][:10])}</a></td>"
            f"<td><a href='/experiment/{html.escape(exp['id'])}'>{html.escape(exp['name'])}</a></td>"
            f"<td class='{_cls(m.get('sharpe'))}'>{html.escape(_fmt(m.get('sharpe')))}</td>"
            f"<td class='{_cls(m.get('total_return'))}'>{html.escape(_fmt(m.get('total_return')))}</td>"
            f"<td class='{_cls(m.get('max_drawdown'))}'>{html.escape(_fmt(m.get('max_drawdown')))}</td>"
            f"<td>{html.escape(_fmt(m.get('srsi')))}</td>"
            f"<td class='mono'>{html.escape(json.dumps(exp.get('params') or {}, sort_keys=True))}</td>"
            "</tr>"
        )

    chart = json.dumps({
        "labels": [e["name"][:18] for e in experiments],
        "sharpes": sharpes,
        "returns": returns,
        "dds": dds,
    })
    best_link = (
        f"<a href='/experiment/{html.escape(best['id'])}'>{html.escape(best['name'])}</a>"
        if best else "—"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>QL · {html.escape(strategy)}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>{_bb_css()}</style>
</head>
<body>
  <div class="topbar">
    <div class="brand"><a href="/">QuantVault</a> <span>STRATEGY</span></div>
    <span class="pill">{html.escape(strategy)}</span>
    <span class="pill">{len(experiments)} RUNS</span>
  </div>
  <div class="wrap">
    <h1>{html.escape(strategy)}</h1>
    <div class="sub">Strategy book · compare parameterizations and risk</div>
    <div class="grid grid-kpi" style="margin: .85rem 0;">
      {_kpi("Runs", len(experiments), digits=0, force_class="amber")}
      {_kpi("Avg Sharpe", avg_sharpe)}
      {_kpi("Best Sharpe", max(valid_s) if valid_s else None)}
      {_kpi("Worst Sharpe", min(valid_s) if valid_s else None)}
      <div class="kpi"><div class="label">Best run</div><div class="value amber" style="font-size:.9rem;">{best_link}</div></div>
      {_kpi("With metrics", len(valid_s), digits=0)}
    </div>
    <div class="panel" style="margin-bottom:.75rem;">
      <h2>Cross-section</h2>
      <div class="chart-box"><canvas id="cross"></canvas></div>
    </div>
    <div class="panel table-wrap">
      <h2>All runs</h2>
      <table>
        <thead><tr><th>ID</th><th>Name</th><th>Sharpe</th><th>Return</th><th>Max DD</th><th>SRSI</th><th>Params</th></tr></thead>
        <tbody>{''.join(rows) or '<tr><td colspan="7" class="empty">No runs</td></tr>'}</tbody>
      </table>
    </div>
  </div>
<script>
const data = {chart};
new Chart(document.getElementById('cross'), {{
  type:'bar',
  data:{{
    labels:data.labels,
    datasets:[
      {{ label:'Sharpe', data:data.sharpes, backgroundColor:'#ff9f1a' }},
      {{ label:'Return', data:data.returns, backgroundColor:'#3aa0ff' }}
    ]
  }},
  options:{{
    responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ labels:{{ color:'#8b95a5', font:{{ family:'IBM Plex Mono', size:10 }} }} }} }},
    scales:{{
      x:{{ ticks:{{ color:'#8b95a5', font:{{ family:'IBM Plex Mono', size:10 }} }}, grid:{{ color:'#1c2430' }} }},
      y:{{ ticks:{{ color:'#8b95a5', font:{{ family:'IBM Plex Mono', size:10 }} }}, grid:{{ color:'#1c2430' }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""
