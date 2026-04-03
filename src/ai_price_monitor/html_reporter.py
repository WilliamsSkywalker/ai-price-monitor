"""HTML report generator with Chart.js visualizations.

Produces a single self-contained HTML file — no server required.
Chart.js is loaded from CDN.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_price_monitor.models import MonthlyUsage, PriceDiff, PriceSnapshot, Provider, Tier
from ai_price_monitor.reporter import _resolve_output_dir

_TIER_COLORS = {
    Tier.CHEAP: "#22c55e",     # green
    Tier.STANDARD: "#eab308",  # yellow
    Tier.PREMIUM: "#ef4444",   # red
}

_PROVIDER_COLORS = {
    Provider.OPENAI: "#10b981",
    Provider.ANTHROPIC: "#8b5cf6",
    Provider.KIMI: "#3b82f6",
    Provider.DEEPSEEK: "#f59e0b",
}

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI API Price Monitor — $snapshot_date</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; padding: 20px; }
  h1 { font-size: 1.75rem; margin-bottom: 6px; }
  h2 { font-size: 1.2rem; color: var(--accent); margin: 28px 0 12px; }
  h3 { font-size: 1rem; color: var(--muted); margin: 20px 0 8px; }
  .subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 24px; }
  .status-bar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
  .status-badge { padding: 4px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
  .status-ok { background: #14532d; color: #86efac; }
  .status-warn { background: #78350f; color: #fcd34d; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .chart-wrap { position: relative; height: 320px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { background: #1e293b; padding: 10px 12px; text-align: left; color: var(--muted);
       border-bottom: 1px solid var(--border); font-weight: 600; }
  td { padding: 9px 12px; border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #1e293b88; }
  .provider-badge { padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; }
  .tier-cheap { color: #22c55e; } .tier-standard { color: #eab308; } .tier-premium { color: #ef4444; }
  .calc-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 16px; }
  .input-group { display: flex; flex-direction: column; gap: 4px; }
  .input-group label { font-size: 0.8rem; color: var(--muted); }
  .input-group input { background: var(--bg); border: 1px solid var(--border); color: var(--text);
    padding: 8px 12px; border-radius: 8px; font-size: 0.9rem; width: 160px; }
  button { background: var(--accent); color: #fff; border: none; padding: 9px 18px;
    border-radius: 8px; cursor: pointer; font-size: 0.9rem; }
  button:hover { background: #2563eb; }
  .top-cost { font-weight: 700; color: #22c55e; }
  footer { margin-top: 40px; color: var(--muted); font-size: 0.8rem; text-align: center; }
</style>
</head>
<body>
<h1>🤖 AI API Price Monitor</h1>
<p class="subtitle">Snapshot: $snapshot_date &nbsp;|&nbsp; Generated: $generated_at UTC</p>

<div class="status-bar" id="statusBar"></div>

<h2>📊 Price Comparison Charts</h2>
<div class="grid">
  <div class="card">
    <h3>Output Price by Model (USD / 1M tokens)</h3>
    <div class="chart-wrap"><canvas id="chartOutput"></canvas></div>
  </div>
  <div class="card">
    <h3>Input vs Output Price — by Provider</h3>
    <div class="chart-wrap"><canvas id="chartInputOutput"></canvas></div>
  </div>
</div>

$history_chart_html

<h2>📋 All Models</h2>
<div class="card">
  <table id="modelsTable">
    <thead><tr>
      <th>Provider</th><th>Model</th><th>Tier</th>
      <th>Input $/1M</th><th>Output $/1M</th><th>Cache Read</th><th>Context</th>
    </tr></thead>
    <tbody id="modelsBody"></tbody>
  </table>
</div>

<h2>💰 Migration Cost Calculator</h2>
<div class="card">
  <div class="calc-row">
    <div class="input-group">
      <label>Input Tokens / Month</label>
      <input type="number" id="inputTokens" value="10000000" step="1000000">
    </div>
    <div class="input-group">
      <label>Output Tokens / Month</label>
      <input type="number" id="outputTokens" value="3000000" step="500000">
    </div>
    <div class="input-group">
      <label>Cache Read Tokens / Month</label>
      <input type="number" id="cacheTokens" value="0" step="1000000">
    </div>
    <button onclick="recalculate()">Recalculate</button>
  </div>
  <table>
    <thead><tr>
      <th>#</th><th>Provider</th><th>Model</th><th>Tier</th>
      <th>Input Cost</th><th>Output Cost</th><th>Cache Cost</th><th>Total / Month</th>
    </tr></thead>
    <tbody id="costBody"></tbody>
  </table>
</div>

$diff_html

<footer>Generated by <a href="https://github.com/WilliamsSkywalker/ai-price-monitor" style="color:var(--accent)">ai-price-monitor</a></footer>

<script>
const DATA = $json_data;

// Status bar
const sb = document.getElementById('statusBar');
DATA.providers.forEach(p => {
  const el = document.createElement('span');
  el.className = 'status-badge ' + (p.fallback_used ? 'status-warn' : 'status-ok');
  el.textContent = p.provider.charAt(0).toUpperCase() + p.provider.slice(1)
    + (p.fallback_used ? ' ⚠️ fallback' : ' ✅');
  sb.appendChild(el);
});

// Models table
const pColors = $provider_colors;
const tColors = $tier_colors;

function fmtPrice(v) { return v != null ? '$' + v.toFixed(4) : '-'; }
function fmtCtx(v) { if (!v) return '-'; return v >= 1e6 ? (v/1e6)+'M' : (v/1000)+'K'; }

const allModels = DATA.providers.flatMap(p => p.models);
const tbody = document.getElementById('modelsBody');
allModels.forEach(m => {
  const tr = document.createElement('tr');
  const color = pColors[m.provider] || '#888';
  const tierClass = 'tier-' + m.tier;
  tr.innerHTML = `
    <td><span class="provider-badge" style="background:${color}22;color:${color}">${m.provider.toUpperCase()}</span></td>
    <td>${m.model_name}</td>
    <td class="${tierClass}">${m.tier}</td>
    <td>${fmtPrice(m.input_price_per_1m)}</td>
    <td>${fmtPrice(m.output_price_per_1m)}</td>
    <td>${fmtPrice(m.cache_read_price)}</td>
    <td>${fmtCtx(m.context_window)}</td>
  `;
  tbody.appendChild(tr);
});

// Chart 1: Output prices horizontal bar
const chart1Models = [...allModels].sort((a,b) => b.output_price_per_1m - a.output_price_per_1m);
new Chart(document.getElementById('chartOutput'), {
  type: 'bar',
  data: {
    labels: chart1Models.map(m => m.model_name),
    datasets: [{
      label: 'Output $/1M',
      data: chart1Models.map(m => m.output_price_per_1m),
      backgroundColor: chart1Models.map(m => tColors[m.tier] + 'bb'),
      borderColor: chart1Models.map(m => tColors[m.tier]),
      borderWidth: 1,
    }]
  },
  options: {
    indexAxis: 'y',
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
      y: { ticks: { color: '#e2e8f0', font: { size: 11 } }, grid: { color: '#1e293b' } },
    }
  }
});

// Chart 2: Input vs Output grouped by provider
const providers = [...new Set(allModels.map(m => m.provider))];
const avgInput = providers.map(p => {
  const ms = allModels.filter(m => m.provider === p);
  return ms.reduce((s,m) => s + m.input_price_per_1m, 0) / ms.length;
});
const avgOutput = providers.map(p => {
  const ms = allModels.filter(m => m.provider === p);
  return ms.reduce((s,m) => s + m.output_price_per_1m, 0) / ms.length;
});
new Chart(document.getElementById('chartInputOutput'), {
  type: 'bar',
  data: {
    labels: providers.map(p => p.charAt(0).toUpperCase() + p.slice(1)),
    datasets: [
      { label: 'Avg Input $/1M', data: avgInput, backgroundColor: '#3b82f688', borderColor: '#3b82f6', borderWidth: 1 },
      { label: 'Avg Output $/1M', data: avgOutput, backgroundColor: '#8b5cf688', borderColor: '#8b5cf6', borderWidth: 1 },
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#e2e8f0' } } },
    scales: {
      x: { ticks: { color: '#e2e8f0' }, grid: { color: '#1e293b' } },
      y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' } },
    }
  }
});

// Cost calculator
function recalculate() {
  const inTok = parseFloat(document.getElementById('inputTokens').value) || 0;
  const outTok = parseFloat(document.getElementById('outputTokens').value) || 0;
  const cacheTok = parseFloat(document.getElementById('cacheTokens').value) || 0;

  const estimates = allModels.map(m => {
    const ic = (inTok / 1e6) * m.input_price_per_1m;
    const oc = (outTok / 1e6) * m.output_price_per_1m;
    const cc = (cacheTok / 1e6) * (m.cache_read_price || 0);
    return { ...m, ic, oc, cc, total: ic + oc + cc };
  }).sort((a, b) => a.total - b.total);

  const cb = document.getElementById('costBody');
  cb.innerHTML = '';
  estimates.forEach((est, i) => {
    const tr = document.createElement('tr');
    const color = pColors[est.provider] || '#888';
    const isTop = i === 0;
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><span class="provider-badge" style="background:${color}22;color:${color}">${est.provider.toUpperCase()}</span></td>
      <td>${est.model_name}</td>
      <td class="tier-${est.tier}">${est.tier}</td>
      <td>$${'${est.ic.toFixed(2)}'}</td>
      <td>$${'${est.oc.toFixed(2)}'}</td>
      <td>$${'${est.cc.toFixed(2)}'}</td>
      <td class="${isTop ? 'top-cost' : ''}">$${'${est.total.toFixed(2)}'}</td>
    `;
    cb.appendChild(tr);
  });
}
recalculate();
</script>
</body>
</html>
"""


def _build_history_chart(snapshots: list[PriceSnapshot]) -> str:
    if len(snapshots) < 2:
        return ""

    # Build per-model price history
    all_model_ids = list(
        {m.model_id for s in snapshots for m in s.get_all_models()}
    )
    # Just show top 6 models by name length for readability
    all_model_ids = sorted(all_model_ids)[:6]

    labels = [s.snapshot_date for s in snapshots]
    datasets = []
    colors = ["#3b82f6", "#ef4444", "#22c55e", "#eab308", "#8b5cf6", "#f59e0b"]

    for i, mid in enumerate(all_model_ids):
        data_points = []
        for s in snapshots:
            model = next((m for m in s.get_all_models() if m.model_id == mid), None)
            data_points.append(model.output_price_per_1m if model else None)

        datasets.append({
            "label": mid,
            "data": data_points,
            "borderColor": colors[i % len(colors)],
            "backgroundColor": colors[i % len(colors)] + "33",
            "tension": 0.3,
            "fill": False,
            "spanGaps": True,
        })

    chart_data = {"labels": labels, "datasets": datasets}

    return f"""
<h2>📈 Historical Price Trends</h2>
<div class="card">
  <h3>Output Price Over Time (USD / 1M tokens)</h3>
  <div class="chart-wrap"><canvas id="chartHistory"></canvas></div>
</div>
<script>
new Chart(document.getElementById('chartHistory'), {{
  type: 'line',
  data: {json.dumps(chart_data)},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#e2e8f0' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
    }}
  }}
}});
</script>"""


def _build_diff_html(diff: PriceDiff | None) -> str:
    if not diff or not diff.has_changes:
        return ""

    rows = []
    for ch in diff.changed_models:
        direction = "📉" if ch.pct_change < 0 else "📈"
        color = "#22c55e" if ch.pct_change < 0 else "#ef4444"
        rows.append(
            f"<tr><td>{ch.provider.value.upper()}</td><td>{ch.model_name}</td>"
            f"<td>{ch.field}</td><td>${ch.old_value:.4f}</td><td>${ch.new_value:.4f}</td>"
            f"<td style='color:{color}'>{direction} {ch.pct_change:+.1f}%</td></tr>"
        )

    if not rows:
        return ""

    return f"""
<h2>🔄 Price Changes (vs {diff.old_date})</h2>
<div class="card">
<table>
<thead><tr><th>Provider</th><th>Model</th><th>Field</th><th>Old</th><th>New</th><th>Change</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>"""


def generate_html(
    snapshot: PriceSnapshot,
    diff: PriceDiff | None = None,
    historical_snapshots: list[PriceSnapshot] | None = None,
) -> str:
    """Generate a complete self-contained HTML report string."""
    # Build JSON data for JS
    json_data = json.dumps(
        {
            "providers": [
                {
                    "provider": p.provider.value,
                    "source_url": p.source_url,
                    "scraped_at": p.scraped_at.isoformat(),
                    "scrape_succeeded": p.scrape_succeeded,
                    "fallback_used": p.fallback_used,
                    "models": [
                        {
                            "model_id": m.model_id,
                            "model_name": m.model_name,
                            "provider": m.provider.value,
                            "tier": m.tier.value,
                            "input_price_per_1m": m.input_price_per_1m,
                            "output_price_per_1m": m.output_price_per_1m,
                            "cache_read_price": m.cache_read_price,
                            "context_window": m.context_window,
                        }
                        for m in p.models
                    ],
                }
                for p in snapshot.providers
            ]
        },
        indent=2,
    )

    provider_colors_json = json.dumps({p.value: c for p, c in _PROVIDER_COLORS.items()})
    tier_colors_json = json.dumps({t.value: c for t, c in _TIER_COLORS.items()})

    history_chart_html = _build_history_chart(historical_snapshots or [snapshot])
    diff_html = _build_diff_html(diff)

    # Fix the JS template string issue by manually replacing dollar signs in JS
    template_str = _HTML_TEMPLATE.replace("${'${est.ic.toFixed(2)}'}", "${est.ic.toFixed(2)}")
    template_str = template_str.replace("${'${est.oc.toFixed(2)}'}", "${est.oc.toFixed(2)}")
    template_str = template_str.replace("${'${est.cc.toFixed(2)}'}", "${est.cc.toFixed(2)}")
    template_str = template_str.replace("${'${est.total.toFixed(2)}'}", "${est.total.toFixed(2)}")

    # Use a manual substitution to avoid Template conflicting with JS ${...}
    result = template_str
    result = result.replace("$snapshot_date", snapshot.snapshot_date)
    result = result.replace(
        "$generated_at",
        snapshot.generated_at.strftime("%Y-%m-%d %H:%M"),
    )
    result = result.replace("$json_data", json_data)
    result = result.replace("$provider_colors", provider_colors_json)
    result = result.replace("$tier_colors", tier_colors_json)
    result = result.replace("$history_chart_html", history_chart_html)
    result = result.replace("$diff_html", diff_html)
    return result


def save_html_report(
    snapshot: PriceSnapshot,
    diff: PriceDiff | None = None,
    historical_snapshots: list[PriceSnapshot] | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Write HTML report to disk and return path."""
    output_dir = _resolve_output_dir(output_dir)
    content = generate_html(snapshot, diff, historical_snapshots)
    path = output_dir / f"{snapshot.snapshot_date}_report.html"
    path.write_text(content, encoding="utf-8")
    return path
