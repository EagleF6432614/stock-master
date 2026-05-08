"""
Polymarket 单市场深度分析 HTML 页面 v0.2

输出:
- Header (市场标题、当前概率、图标)
- 价格历史曲线图(SVG/Chart.js)
- 信号解读卡片
- 大户持仓表(YES/NO 各 Top 5)
- 最近成交流水

输出路径: ./reports/polymarket_<slug>_YYYYMMDD_HHMM.html
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from polymarket_analyzer import analyze_market_depth, _safe_float

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
}
.container { max-width: 980px; margin: 0 auto; padding: 20px 16px; }

.header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 1px solid #2a2a3e;
    padding: 24px 0;
}
.header-inner { display: flex; align-items: center; gap: 20px; }
.market-icon {
    width: 64px; height: 64px;
    border-radius: 12px; flex-shrink: 0;
    background-size: cover; background-position: center;
    background-color: #252540;
}
.header-meta { flex: 1; }
.header-title {
    font-size: 1.25em; font-weight: 700;
    color: #e0e0e0; line-height: 1.4;
}
.header-sub { color: #888; font-size: 0.85em; margin-top: 6px; }

.section {
    background: #1a1a2e;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    border: 1px solid #2a2a3e;
}
.section-title {
    font-size: 1.05em; font-weight: 600;
    margin-bottom: 14px; color: #e0e0e0;
}

/* Probability bar */
.prob-row {
    display: flex; gap: 12px; flex-wrap: wrap;
    margin-bottom: 16px;
}
.prob-card {
    flex: 1; min-width: 160px;
    background: #141428;
    border-radius: 8px;
    padding: 14px 16px;
}
.prob-label { color: #888; font-size: 0.78em; }
.prob-value { font-size: 1.6em; font-weight: 700; margin-top: 4px; }
.prob-yes .prob-value { color: #26a69a; }
.prob-no .prob-value { color: #ef5350; }
.prob-sub { color: #888; font-size: 0.78em; margin-top: 4px; }

/* Stats row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 10px;
}
.stat-card {
    background: #141428;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
}
.stat-label { color: #888; font-size: 0.74em; margin-top: 4px; }
.stat-value { color: #e0e0e0; font-size: 1.05em; font-weight: 600; }

/* Chart */
.chart-container {
    background: #141428;
    border-radius: 8px;
    padding: 16px;
    height: 360px;
}

/* Signals */
.signal-list {
    display: flex; flex-direction: column; gap: 8px;
}
.signal-item {
    background: #141428;
    border-left: 3px solid #42a5f5;
    border-radius: 6px;
    padding: 12px 14px;
    color: #c0c0d0;
    font-size: 0.92em;
    line-height: 1.5;
}

/* Holder table */
.holder-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
.holder-col h4 {
    font-size: 0.95em;
    margin-bottom: 8px;
}
.holder-col h4.yes { color: #26a69a; }
.holder-col h4.no { color: #ef5350; }
.holder-row {
    display: flex; justify-content: space-between;
    background: #141428;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 6px;
    font-size: 0.85em;
}
.holder-name { color: #c0c0d0; flex: 1; overflow: hidden; text-overflow: ellipsis; }
.holder-amount { color: #e0e0e0; font-weight: 600; margin-left: 12px; }

/* Trades */
.trade-list { font-family: monospace; font-size: 0.82em; }
.trade-row {
    display: flex; justify-content: space-between;
    background: #141428;
    border-radius: 4px;
    padding: 6px 12px;
    margin-bottom: 4px;
}
.trade-side-buy { color: #26a69a; font-weight: 600; }
.trade-side-sell { color: #ef5350; font-weight: 600; }
.trade-meta { color: #888; }

/* Footer */
.footer {
    text-align: center; color: #555; font-size: 0.75em;
    padding: 24px 0 12px;
    border-top: 1px solid #1f1f35;
    margin-top: 8px;
}
.footer a { color: #42a5f5; text-decoration: none; }
.cta-btn {
    display: inline-block;
    padding: 10px 20px;
    background: #1976d2;
    color: #fff;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.9em;
    margin-top: 8px;
    border: none;
    transition: background 0.2s;
}
.cta-btn:hover {
    background: #1565c0;
}

/* AI Analysis Section */
.ai-section {
    background: linear-gradient(135deg, #1a1a2e 0%, #1f1f3a 100%);
    border: 1px solid #2a2a4e;
}
.ai-badge {
    display: inline-block;
    background: #1976d2;
    color: #fff;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72em;
    font-weight: 600;
    margin-left: 8px;
    vertical-align: middle;
}
.ai-verdict {
    background: #141428;
    border-left: 4px solid #1976d2;
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.ai-verdict-title {
    font-size: 0.78em;
    color: #888;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.ai-verdict-text {
    font-size: 1.05em;
    color: #e0e0e0;
    font-weight: 600;
    line-height: 1.5;
}
.ai-verdict-sub {
    font-size: 0.88em;
    color: #aaa;
    margin-top: 8px;
    line-height: 1.6;
}
.ai-score-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 700;
    margin-left: 8px;
}
.score-pos { background: rgba(38,166,154,0.2); color: #26a69a; }
.score-neg { background: rgba(239,83,80,0.2); color: #ef5350; }
.score-neu { background: rgba(160,160,176,0.2); color: #a0a0b0; }

.ai-dim-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}
.ai-dim-card {
    background: #141428;
    border-radius: 8px;
    padding: 14px 16px;
    border-top: 3px solid #1976d2;
}
.ai-dim-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px;
}
.ai-dim-title {
    font-weight: 600; color: #e0e0e0;
    font-size: 0.95em;
}
.ai-dim-logic {
    color: #a8a8b8;
    font-size: 0.85em;
    line-height: 1.6;
}
.ai-dim-logic strong { color: #c8c8d8; }
.ai-action {
    background: rgba(25,118,210,0.1);
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 12px;
}
.ai-action-title {
    font-size: 0.78em;
    color: #42a5f5;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.ai-action-text {
    color: #e0e0e0;
    font-size: 0.92em;
    line-height: 1.6;
}

/* Claude section */
.claude-section {
    background: linear-gradient(135deg, #1e1a2e 0%, #281f3a 100%);
    border: 1px solid #3a2a5e;
}
.claude-content {
    color: #d0d0e0;
    font-size: 0.93em;
    line-height: 1.75;
}
.claude-content h1 {
    font-size: 1.25em; color: #e0e0e0;
    margin: 20px 0 10px; font-weight: 700;
    border-bottom: 1px solid #2a2a4e; padding-bottom: 6px;
}
.claude-content h2 {
    font-size: 1.12em; color: #b494ff;
    margin: 18px 0 10px; font-weight: 700;
}
.claude-content h3 {
    font-size: 1.02em; color: #c0a4ff;
    margin: 14px 0 8px; font-weight: 600;
}
.claude-content p {
    margin: 8px 0;
}
.claude-content ul {
    margin: 8px 0 12px; padding-left: 24px;
}
.claude-content li {
    margin: 4px 0;
}
.claude-content strong {
    color: #f0e0ff; font-weight: 700;
}
.claude-content em {
    color: #b494ff; font-style: italic;
}
.claude-content code {
    background: rgba(124,77,255,0.15);
    padding: 1px 6px;
    border-radius: 3px;
    font-family: 'SF Mono', Monaco, monospace;
    font-size: 0.88em;
    color: #d4b0ff;
}
.claude-content blockquote {
    border-left: 3px solid #7c4dff;
    background: rgba(124,77,255,0.08);
    margin: 10px 0;
    padding: 10px 16px;
    color: #c0c0d0;
    border-radius: 0 6px 6px 0;
}

@media (max-width: 640px) {
    .header-inner { flex-direction: column; align-items: flex-start; }
    .holder-grid { grid-template-columns: 1fr; }
}
"""


def _fmt_money(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _fmt_ts(ts: int) -> str:
    """unix timestamp → 'MM-DD HH:MM' """
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def _render_header(market: Dict[str, Any]) -> str:
    icon = market.get("image") or ""
    icon_style = f'background-image: url("{icon}");' if icon else ""
    end_str = ""
    if market.get("days_until_end"):
        end_str = f"⏰ {market['days_until_end']:.1f} 天后结束"

    return f"""
    <div class="header">
        <div class="container">
            <div class="header-inner">
                <div class="market-icon" style="{icon_style}"></div>
                <div class="header-meta">
                    <div class="header-title">{market.get('question', '—')}</div>
                    <div class="header-sub">
                        24h 成交 {_fmt_money(market.get('volume_24h', 0))}  ·
                        流动性 {_fmt_money(market.get('liquidity', 0))}  ·
                        {end_str}
                    </div>
                </div>
            </div>
        </div>
    </div>"""


def _render_probabilities(market: Dict[str, Any]) -> str:
    outcomes = market.get("outcomes", {})
    cards = []
    for k, v in outcomes.items():
        css_class = "prob-yes" if k.lower() == "yes" else "prob-no" if k.lower() == "no" else ""
        cards.append(f"""
        <div class="prob-card {css_class}">
            <div class="prob-label">{k}</div>
            <div class="prob-value">{v:.1%}</div>
            <div class="prob-sub">隐含概率</div>
        </div>""")
    return f'<div class="prob-row">{"".join(cards)}</div>'


def _render_stats(signals: Dict[str, Any], market: Dict[str, Any]) -> str:
    cards = []

    if "price_change_24h_pct" in signals:
        v = signals["price_change_24h_pct"]
        color = "#26a69a" if v >= 0 else "#ef5350"
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:{color}">{v:+.1f}%</div>
            <div class="stat-label">24h 变化</div>
        </div>""")

    if "price_change_7d_pct" in signals:
        v = signals["price_change_7d_pct"]
        color = "#26a69a" if v >= 0 else "#ef5350"
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:{color}">{v:+.1f}%</div>
            <div class="stat-label">7天 变化</div>
        </div>""")

    if "volatility" in signals:
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-value">{signals['volatility']:.3f}</div>
            <div class="stat-label">波动率(σ)</div>
        </div>""")

    net_yes = signals.get("recent_net_yes_flow")
    if net_yes is not None:
        color = "#26a69a" if net_yes >= 0 else "#ef5350"
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:{color}">{net_yes:+,.0f}</div>
            <div class="stat-label">近期 YES 净流入</div>
        </div>""")

    conc_yes = signals.get("holder_concentration_outcome_0")
    if conc_yes is not None:
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-value">{conc_yes}%</div>
            <div class="stat-label">YES Top5 集中度</div>
        </div>""")

    if not cards:
        return ""
    return f"""
    <div class="section">
        <div class="section-title">📊 关键指标</div>
        <div class="stats-row">{"".join(cards)}</div>
    </div>"""


def _render_chart(history: List[Dict[str, Any]]) -> str:
    if not history:
        return ""
    # 准备 chart.js 数据
    points = [{"t": h.get("t"), "p": h.get("p")} for h in history if h.get("t") and h.get("p") is not None]
    if not points:
        return ""

    # 抽样：超过 200 点就降采样到 200 点(避免图表卡顿)
    if len(points) > 200:
        step = len(points) // 200
        points = points[::step]

    data_json = json.dumps(points)
    return f"""
    <div class="section">
        <div class="section-title">📈 价格历史曲线 (YES 概率)</div>
        <div class="chart-container">
            <canvas id="priceChart"></canvas>
        </div>
        <script>
        const points = {data_json};
        const labels = points.map(p => {{
            const d = new Date(p.t * 1000);
            return (d.getMonth()+1) + '/' + d.getDate() + ' ' + d.getHours() + ':' + String(d.getMinutes()).padStart(2,'0');
        }});
        const values = points.map(p => p.p);
        const ctx = document.getElementById('priceChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: 'YES 概率',
                    data: values,
                    borderColor: '#42a5f5',
                    backgroundColor: 'rgba(66,165,245,0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ mode: 'index', intersect: false }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#888', maxTicksLimit: 8 }},
                        grid: {{ color: '#252540' }}
                    }},
                    y: {{
                        ticks: {{
                            color: '#888',
                            callback: function(v) {{ return (v*100).toFixed(0)+'%'; }}
                        }},
                        grid: {{ color: '#252540' }}
                    }}
                }},
                plugins: {{
                    legend: {{ labels: {{ color: '#c0c0d0' }} }},
                    tooltip: {{
                        callbacks: {{
                            label: ctx => 'YES: ' + (ctx.parsed.y * 100).toFixed(2) + '%'
                        }}
                    }}
                }}
            }}
        }});
        </script>
    </div>"""


def _render_signals(interp: List[str]) -> str:
    if not interp:
        return ""
    items = "".join(f'<div class="signal-item">{s}</div>' for s in interp)
    return f"""
    <div class="section">
        <div class="section-title">🧠 信号解读</div>
        <div class="signal-list">{items}</div>
    </div>"""


def _render_holders(holders_data: List[Dict[str, Any]]) -> str:
    if not holders_data:
        return ""
    yes_holders, no_holders = [], []
    for token_data in holders_data:
        h_list = token_data.get("holders", [])
        if not h_list:
            continue
        if h_list[0].get("outcomeIndex") == 0:
            yes_holders = h_list[:5]
        elif h_list[0].get("outcomeIndex") == 1:
            no_holders = h_list[:5]

    def render_col(label: str, css: str, holders: List[Dict[str, Any]]) -> str:
        if not holders:
            return f'<div class="holder-col"><h4 class="{css}">{label}</h4><div class="empty">无数据</div></div>'
        rows = []
        for h in holders:
            name = h.get("name") or h.get("pseudonym") or h.get("proxyWallet", "")[:10]
            amount = _safe_float(h.get("amount"))
            rows.append(f'<div class="holder-row"><span class="holder-name">{name}</span><span class="holder-amount">{amount:,.0f}</span></div>')
        return f'<div class="holder-col"><h4 class="{css}">{label}</h4>{"".join(rows)}</div>'

    return f"""
    <div class="section">
        <div class="section-title">👥 大户持仓 Top 5</div>
        <div class="holder-grid">
            {render_col('YES 多头', 'yes', yes_holders)}
            {render_col('NO 空头', 'no', no_holders)}
        </div>
    </div>"""


def _render_trades(trades: List[Dict[str, Any]]) -> str:
    if not trades:
        return ""
    rows = []
    for t in trades[:15]:
        side = t.get("side", "")
        outcome = t.get("outcome", "")
        size = _safe_float(t.get("size"))
        price = _safe_float(t.get("price"))
        ts = t.get("timestamp", 0)
        name = t.get("name") or t.get("pseudonym") or "—"
        side_class = "trade-side-buy" if side == "BUY" else "trade-side-sell"
        rows.append(f"""
        <div class="trade-row">
            <span><span class="{side_class}">{side}</span> {outcome} · {size:,.0f}股 @ {price:.3f}</span>
            <span class="trade-meta">{name[:20]} · {_fmt_ts(ts)}</span>
        </div>""")
    return f"""
    <div class="section">
        <div class="section-title">⚡ 最近成交</div>
        <div class="trade-list">{"".join(rows)}</div>
    </div>"""


def _render_ai_analysis(ai: Dict[str, Any]) -> str:
    """渲染 AI 四维分析板块。"""
    if not ai:
        return ""

    composite = ai.get("composite_score", 0)
    verdict = ai.get("verdict", "")
    action = ai.get("action", "")
    dims = ai.get("dimensions", [])
    tags = ai.get("tags", [])

    # 综合得分 pill
    if composite > 0.2:
        composite_pill = '<span class="ai-score-pill score-pos">+{:.2f}</span>'.format(composite)
    elif composite < -0.2:
        composite_pill = '<span class="ai-score-pill score-neg">{:.2f}</span>'.format(composite)
    else:
        composite_pill = '<span class="ai-score-pill score-neu">{:+.2f}</span>'.format(composite)

    tags_html = ""
    if tags:
        tag_chips = " ".join(
            f'<span style="display:inline-block;padding:2px 8px;background:rgba(66,165,245,0.15);color:#42a5f5;border-radius:4px;font-size:0.74em;margin-right:4px">{t}</span>'
            for t in tags
        )
        tags_html = f'<div style="margin-top:8px">{tag_chips}</div>'

    # 维度卡片
    dim_cards = []
    for d in dims:
        name = d.get("name", "—")
        score = d.get("score", 0)
        facts = d.get("facts", [])
        mech = d.get("mechanism", "")
        conclusion = d.get("conclusion", "")
        pill = d.get("pill", "neu")

        sign = "+" if score >= 0 else ""
        score_html = f'<span class="ai-score-pill score-{pill}">{sign}{score:.2f}</span>'

        facts_html = ""
        if facts:
            facts_html = "<br>".join(f"• {f}" for f in facts)

        dim_cards.append(f"""
        <div class="ai-dim-card">
            <div class="ai-dim-header">
                <div class="ai-dim-title">{name}</div>
                {score_html}
            </div>
            <div class="ai-dim-logic">
                <strong>事实</strong><br>{facts_html}<br>
                <strong style="margin-top:8px;display:inline-block">机制</strong><br>{mech}<br>
                <strong style="margin-top:8px;display:inline-block">结论</strong>: <span style="color:#e0e0e0">{conclusion}</span>
            </div>
        </div>""")

    return f"""
    <div class="section ai-section">
        <div class="section-title">
            📊 数据信号
        </div>

        <div class="ai-verdict">
            <div class="ai-verdict-title">综合判断 {composite_pill}</div>
            <div class="ai-verdict-text">{verdict}</div>
            {tags_html}
        </div>

        <div class="ai-dim-grid">
            {"".join(dim_cards)}
        </div>

        <div class="ai-action">
            <div class="ai-action-title">💡 操作建议</div>
            <div class="ai-action-text">{action}</div>
        </div>
    </div>"""


def _md_to_html(md: str) -> str:
    """简易 markdown → HTML 转换（标题/列表/粗体/段落）。不依赖外部库。"""
    if not md:
        return ""
    lines = md.split("\n")
    html = []
    in_ul = False
    for raw in lines:
        line = raw.rstrip()
        if not line:
            if in_ul:
                html.append("</ul>")
                in_ul = False
            continue

        # 标题
        if line.startswith("### "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h3>{_inline_md(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h2>{_inline_md(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h1>{_inline_md(line[2:])}</h1>")
        # 列表
        elif line.lstrip().startswith(("- ", "* ")):
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            content = line.lstrip()[2:]
            html.append(f"<li>{_inline_md(content)}</li>")
        # 引用
        elif line.startswith("> "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<blockquote>{_inline_md(line[2:])}</blockquote>")
        else:
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<p>{_inline_md(line)}</p>")

    if in_ul:
        html.append("</ul>")
    return "\n".join(html)


def _inline_md(text: str) -> str:
    """处理行内 markdown：**bold**, *italic*, `code`"""
    import re
    # **bold**
    text = re.sub(r"\*\*([^\*]+)\*\*", r"<strong>\1</strong>", text)
    # *italic*  (避免和 ** 冲突)
    text = re.sub(r"(?<!\*)\*([^\*]+)\*(?!\*)", r"<em>\1</em>", text)
    # `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _render_claude_analysis(md_content: str) -> str:
    """渲染 Claude Code 生成的 markdown 深度解读。"""
    if not md_content or not md_content.strip():
        return ""
    body_html = _md_to_html(md_content)
    return f"""
    <div class="section claude-section">
        <div class="section-title">
            💡 深度解读
        </div>
        <div class="claude-content">
            {body_html}
        </div>
    </div>"""


def _render_footer(market: Dict[str, Any]) -> str:
    return f"""
    <div class="footer">
        <div class="container">
            <a href="{market.get('url', '#')}" target="_blank" class="cta-btn">在 Polymarket 打开 →</a><br><br>
            数据来源: Polymarket Gamma · CLOB · Data API<br>
            预测市场仅供参考，请理性评估，注意 gas 费、流动性及结算风险<br>
            Generated by Stock Master · {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>"""


def generate_market_report(slug: str, open_browser: bool = True,
                           history_interval: str = "1m",
                           claude_analysis: Optional[str] = None) -> Optional[str]:
    """
    生成单市场深度报告 HTML，返回路径。slug 不存在返回 None。

    Args:
        slug: Polymarket 市场 slug
        open_browser: 是否自动打开浏览器
        history_interval: 价格历史粒度 (1m/1w/1d/6h/1h/max)
        claude_analysis: 可选，Claude Code 生成的 markdown 深度解读文本，会渲染为独立板块
    """
    print(f"[polymarket depth] 分析 {slug}...")
    analysis = analyze_market_depth(slug, history_interval=history_interval)
    if not analysis:
        print(f"[polymarket depth] 未找到市场: {slug}")
        return None

    market = analysis["market"]
    history = analysis.get("history", [])
    holders = analysis.get("holders", [])
    trades = analysis.get("trades", [])
    signals = analysis.get("signals", {})
    interp = analysis.get("interp", [])
    ai = analysis.get("ai", {})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{market['question']} - Polymarket 深度解读</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>{CSS}</style>
</head>
<body>
    {_render_header(market)}
    <div class="container">
        <div class="section">
            <div class="section-title">💲 当前概率</div>
            {_render_probabilities(market)}
        </div>
        {_render_claude_analysis(claude_analysis)}
        {_render_ai_analysis(ai)}
        {_render_stats(signals, market)}
        {_render_chart(history)}
        {_render_signals(interp)}
        {_render_holders(holders)}
        {_render_trades(trades)}
    </div>
    {_render_footer(market)}
</body>
</html>"""

    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    safe_slug = slug.replace("/", "_")[:60]
    filename = f"polymarket_{safe_slug}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    filepath = os.path.join(DEFAULT_OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    if open_browser:
        try:
            subprocess.Popen(["open", filepath])
        except Exception:
            pass

    return filepath


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 polymarket_market_report.py <slug> [interval]")
        print("示例: python3 polymarket_market_report.py will-bitcoin-hit-150k-by-june-30-2026")
        sys.exit(1)
    slug = sys.argv[1]
    interval = sys.argv[2] if len(sys.argv) > 2 else "1m"
    path = generate_market_report(slug, history_interval=interval)
    if path:
        print(f"✅ 深度报告: {path}")
    else:
        print("❌ 生成失败")
