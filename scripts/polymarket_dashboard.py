"""
Polymarket Dashboard HTML 生成器 v0.2

输出包含:
- Header (品牌 + 时间戳)
- 分类 Tabs (政治/加密/体育/地缘/科技/经济/娱乐)
- 各分类 Top 标的
- 全局热门市场
- 最近新上线市场

输出路径: ./reports/polymarket_dashboard_YYYYMMDD_HHMM.html
"""

import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List

from polymarket_analyzer import (
    list_trending_markets, list_new_markets, list_by_category,
    CATEGORY_PRESETS, _safe_float,
)

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


# ---------------------------------------------------------------------------
# CSS (复用 market_dashboard 风格 + Polymarket 特化)
# ---------------------------------------------------------------------------

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
}
.container { max-width: 980px; margin: 0 auto; padding: 20px 16px; }

/* Header */
.header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 1px solid #2a2a3e;
    padding: 18px 0;
    text-align: center;
}
.header-title {
    font-size: 1.6em; font-weight: 700;
    background: linear-gradient(90deg, #42a5f5, #ab47bc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.header-sub { color: #888; font-size: 0.85em; margin-top: 4px; }
.header-time { color: #555; font-size: 0.75em; margin-top: 2px; }

/* Section */
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
    display: flex; align-items: center; gap: 8px;
}
.section-title .count {
    font-size: 0.75em; color: #888; font-weight: 400;
}

/* Tabs */
.tabs {
    display: flex; flex-wrap: wrap; gap: 8px;
    margin-bottom: 16px;
}
.tab {
    padding: 8px 16px;
    background: #1a1a2e;
    border: 1px solid #2a2a3e;
    border-radius: 20px;
    color: #aaa;
    cursor: pointer;
    font-size: 0.88em;
    transition: all 0.2s;
}
.tab:hover { background: #252540; color: #fff; }
.tab.active {
    background: linear-gradient(90deg, #42a5f5, #ab47bc);
    color: #fff; border-color: transparent;
}

.tab-content { display: none; }
.tab-content.active { display: block; }

/* Market card */
.market-list { display: flex; flex-direction: column; gap: 10px; }
.market-card {
    background: #141428;
    border-radius: 8px;
    padding: 14px 16px;
    border-left: 3px solid #42a5f5;
    transition: background 0.2s;
}
.market-card:hover { background: #1a1a36; }
.market-card.new { border-left-color: #66bb6a; }
.market-card.crypto { border-left-color: #ab47bc; }
.market-card.politics { border-left-color: #ef5350; }
.market-card.sports { border-left-color: #ffa726; }

.market-question {
    font-size: 0.95em; font-weight: 600;
    color: #e0e0e0; margin-bottom: 8px; line-height: 1.4;
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 12px;
}
.market-question .q-text { flex: 1; }
.market-question a { color: inherit; text-decoration: none; }
.market-question a:hover { color: #1976d2; }

.deep-read-btn {
    flex-shrink: 0;
    background: #1976d2;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 0.74em;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
    font-family: inherit;
}
.deep-read-btn:hover { background: #1565c0; }
.deep-read-btn:active { background: #0d47a1; }

/* Toast */
.toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(120%);
    background: #1976d2;
    color: #fff;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 0.9em;
    font-weight: 500;
    box-shadow: 0 4px 16px rgba(25,118,210,0.4);
    transition: transform 0.3s ease;
    z-index: 9999;
    max-width: 90%;
    text-align: center;
}
.toast.show { transform: translateX(-50%) translateY(0); }

.market-row {
    display: flex; gap: 16px; align-items: center;
    flex-wrap: wrap; font-size: 0.82em;
}
.outcome-bar {
    display: flex; align-items: center; gap: 6px;
    flex: 1; min-width: 200px;
}
.outcome-yes, .outcome-no {
    padding: 3px 10px; border-radius: 6px; font-weight: 600;
}
.outcome-yes { background: rgba(38,166,154,0.15); color: #26a69a; }
.outcome-no { background: rgba(239,83,80,0.15); color: #ef5350; }

.market-stat { color: #888; font-size: 0.82em; }
.market-stat strong { color: #c0c0d0; }

.event-tag {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(160,160,176,0.1);
    border-radius: 4px;
    color: #888; font-size: 0.74em;
    margin-top: 6px;
}

/* Multi-outcome (3+) */
.multi-outcomes {
    display: flex; gap: 6px; flex-wrap: wrap;
    margin: 4px 0;
}
.multi-outcome {
    padding: 3px 10px; border-radius: 6px;
    background: rgba(66,165,245,0.15); color: #42a5f5;
    font-size: 0.78em; font-weight: 500;
}

/* Footer */
.footer {
    text-align: center; color: #555; font-size: 0.75em;
    padding: 24px 0 12px;
    border-top: 1px solid #1f1f35;
    margin-top: 8px;
}
.footer a { color: #42a5f5; text-decoration: none; }

/* Empty state */
.empty {
    text-align: center; color: #666;
    padding: 40px 20px;
    font-size: 0.9em;
}

@media (max-width: 640px) {
    .market-row { gap: 8px; }
    .outcome-bar { min-width: 100%; }
    .tab { padding: 6px 12px; font-size: 0.82em; }
}
"""


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _fmt_money(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _render_market_card(m: Dict[str, Any], variant: str = "") -> str:
    outcomes = m.get("outcomes", {})
    url = m.get("url", "#")
    question = m.get("question", "—")
    slug = m.get("slug", "")
    vol_24h = _fmt_money(m.get("volume_24h", 0))
    liquidity = _fmt_money(m.get("liquidity", 0))

    # 概率显示
    if "Yes" in outcomes and "No" in outcomes:
        yes_p = outcomes["Yes"]
        no_p = outcomes["No"]
        outcome_html = f"""
        <div class="outcome-bar">
            <span class="outcome-yes">YES {yes_p:.1%}</span>
            <span class="outcome-no">NO {no_p:.1%}</span>
        </div>"""
    else:
        # 多选(3+)市场
        chips = []
        for k, v in list(outcomes.items())[:5]:
            chips.append(f'<span class="multi-outcome">{k} {v:.1%}</span>')
        outcome_html = f'<div class="outcome-bar"><div class="multi-outcomes">{"".join(chips)}</div></div>'

    # 事件标签
    event_html = ""
    if m.get("event_title") and m["event_title"] != question:
        event_html = f'<div class="event-tag">📁 {m["event_title"]}</div>'

    # 新市场显示创建时间
    age_html = ""
    if "days_since_created" in m and m["days_since_created"] is not None:
        age = m["days_since_created"]
        if age < 1:
            age_html = f'<span class="market-stat">⏱ {age*24:.0f}小时前</span>'
        else:
            age_html = f'<span class="market-stat">⏱ {age:.1f}天前</span>'

    days_left_html = ""
    if m.get("days_until_end"):
        days = m["days_until_end"]
        if days < 7:
            days_left_html = f'<span class="market-stat" style="color:#ffa726">⏰ {days:.0f}天结束</span>'

    return f"""
    <div class="market-card {variant}">
        <div class="market-question">
            <span class="q-text"><a href="{url}" target="_blank">{question}</a></span>
            <button class="deep-read-btn" onclick="deepRead(this, '{slug}')" title="复制深度解读 prompt 到剪贴板">🔍 深度解读</button>
        </div>
        <div class="market-row">
            {outcome_html}
            <span class="market-stat">24h <strong>{vol_24h}</strong></span>
            <span class="market-stat">流动性 <strong>{liquidity}</strong></span>
            {age_html}
            {days_left_html}
        </div>
        {event_html}
    </div>"""


def _render_market_list(markets: List[Dict[str, Any]], variant: str = "") -> str:
    if not markets:
        return '<div class="empty">暂无数据</div>'
    cards = "\n".join(_render_market_card(m, variant) for m in markets)
    return f'<div class="market-list">{cards}</div>'


def _render_tabs(category_data: Dict[str, List[Dict[str, Any]]]) -> str:
    """渲染分类 tabs。"""
    # tab 按钮
    tab_btns = []
    tab_panels = []
    for i, (cat, markets) in enumerate(category_data.items()):
        active_class = "active" if i == 0 else ""
        tab_btns.append(
            f'<div class="tab {active_class}" onclick="showTab(\'cat_{i}\', this)">{cat} ({len(markets)})</div>'
        )
        # 分类样式映射
        variant = ""
        if cat in ("加密",):
            variant = "crypto"
        elif cat in ("政治", "地缘"):
            variant = "politics"
        elif cat in ("体育",):
            variant = "sports"
        tab_panels.append(
            f'<div id="cat_{i}" class="tab-content {active_class}">{_render_market_list(markets, variant)}</div>'
        )

    return f"""
    <div class="section">
        <div class="section-title">🏷️ 分类视图</div>
        <div class="tabs">{"".join(tab_btns)}</div>
        {"".join(tab_panels)}
    </div>
    """


def _render_header() -> str:
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    return f"""
    <div class="header">
        <div class="container">
            <div class="header-title">Polymarket 看盘</div>
            <div class="header-sub">预测市场标的发现 · 分类浏览 · 深度分析</div>
            <div class="header-time">生成时间: {now}</div>
        </div>
    </div>"""


def _render_footer() -> str:
    return f"""
    <div class="footer">
        <div class="container">
            数据来源: <a href="https://polymarket.com/" target="_blank">Polymarket</a>
            (Gamma API · CLOB API · Data API)<br>
            预测市场仅供参考，请理性评估，注意 gas 费、流动性及结算风险<br>
            Generated by Stock Master · {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>"""


JS = """
function showTab(id, btn) {
    var contents = document.getElementsByClassName('tab-content');
    for (var i = 0; i < contents.length; i++) {
        contents[i].classList.remove('active');
    }
    var tabs = btn.parentNode.getElementsByClassName('tab');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].classList.remove('active');
    }
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
}

function deepRead(btn, slug) {
    var prompt = '深度解读 polymarket 市场: ' + slug;
    var success = false;

    // 优先用现代 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(prompt).then(function() {
            showToast('✅ 已复制到剪贴板！请回到对话粘贴 (Cmd+V) 并发送');
        }).catch(function() {
            fallbackCopy(prompt);
        });
    } else {
        fallbackCopy(prompt);
    }
}

function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showToast('✅ 已复制到剪贴板！请回到对话粘贴 (Cmd+V) 并发送');
    } catch (e) {
        showToast('❌ 复制失败，请手动复制: ' + text);
    }
    document.body.removeChild(ta);
}

function showToast(msg) {
    var existing = document.querySelector('.toast');
    if (existing) existing.remove();
    var t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function() { t.classList.add('show'); }, 10);
    setTimeout(function() {
        t.classList.remove('show');
        setTimeout(function() { t.remove(); }, 300);
    }, 3500);
}
"""


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def generate_dashboard(open_browser: bool = True) -> str:
    """生成主看板 HTML 并(可选)在浏览器中打开。返回文件路径。"""
    print("[polymarket dashboard] 拉取 trending...")
    trending = list_trending_markets(limit=15)

    print("[polymarket dashboard] 拉取 new...")
    new_markets = list_new_markets(days=7, limit=10, min_liquidity=1000)

    print("[polymarket dashboard] 拉取分类...")
    category_data: Dict[str, List[Dict[str, Any]]] = {}
    for cat in CATEGORY_PRESETS.keys():
        markets = list_by_category(cat, limit=8, min_liquidity=2000)
        if markets:
            category_data[cat] = markets

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket 看盘 - Stock Master</title>
    <style>{CSS}</style>
</head>
<body>
    {_render_header()}
    <div class="container">
        <div class="section">
            <div class="section-title">📈 全网热门 <span class="count">按 24h 成交量</span></div>
            {_render_market_list(trending)}
        </div>

        {_render_tabs(category_data)}

        <div class="section">
            <div class="section-title">🆕 最近 7 天新上线 <span class="count">{len(new_markets)} 个</span></div>
            {_render_market_list(new_markets, "new")}
        </div>
    </div>
    {_render_footer()}
    <script>{JS}</script>
</body>
</html>"""

    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    filename = f"polymarket_dashboard_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
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
    path = generate_dashboard()
    print(f"✅ 看板已生成: {path}")
