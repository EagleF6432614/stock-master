"""
大盘数据 Dashboard 生成模块 v1.0

功能:
- 从 Day1 Global API 获取市场数据和分析
- 生成自包含的暗色主题 HTML Dashboard
- 卡片式布局: 大盘概览、详细数据表、情绪面板、BTC 信号、分析、催化剂、新闻
- 仅使用 Python 标准库，无外部依赖

数据源:
- https://brief.day1global.xyz/api/market-data — 股票、加密货币、指数、情绪、BTC 指标
- https://brief.day1global.xyz/api/analysis — 宏观分析、加密分析、操作建议、催化剂、新闻
"""

import json
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://brief.day1global.xyz/api"
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Desktop/AI编程/stock master/reports")

# 大盘概览卡片使用的 ticker（按顺序）
OVERVIEW_TICKERS = {"VOO", "QQQM", "VIX", "GOLD", "BTC", "ETH"}

# 新闻类别 → 颜色映射 (API 返回中文 tag)
NEWS_CATEGORY_COLORS = {
    "加密": "#ab47bc",
    "财报": "#66bb6a",
    "避险": "#ffa726",
    "科技": "#42a5f5",
    "宏观": "#ef5350",
    "政策": "#ff7043",
    "市场": "#26c6da",
    # English fallbacks
    "Crypto": "#ab47bc",
    "Earnings": "#66bb6a",
    "Hedging": "#ffa726",
    "Tech": "#42a5f5",
    "Macro": "#ef5350",
    "Policy": "#ff7043",
    "Markets": "#26c6da",
}

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def fetch_api(endpoint: str, timeout: int = 15) -> Dict[str, Any]:
    """GET https://brief.day1global.xyz/api/{endpoint} 并返回解析后的 JSON dict。

    出错时返回空 dict，不抛异常。
    """
    url = f"{API_BASE}/{endpoint}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stock-master/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, ValueError) as exc:
        print(f"[market_dashboard] fetch_api({endpoint}) failed: {exc}")
        return {}


def fetch_all_data() -> Dict[str, Any]:
    """调用两个 API 端点，返回 {'market': {...}, 'analysis': {...}}"""
    market = fetch_api("market-data")
    analysis = fetch_api("analysis")
    return {"market": market, "analysis": analysis}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_change(val: Any) -> Tuple[float, str]:
    """解析涨跌值，返回 (float_value, css_class)。

    val 可以是 float、int、str (如 "+6.52%" 或 "-0.25%")。
    """
    if val is None:
        return 0.0, "neutral"
    if isinstance(val, str):
        cleaned = val.replace("%", "").replace("+", "").strip()
        try:
            v = float(cleaned)
        except ValueError:
            return 0.0, "neutral"
    else:
        try:
            v = float(val)
        except (TypeError, ValueError):
            return 0.0, "neutral"
    css = "up" if v >= 0 else "down"
    return v, css


def _fmt_price(val: Any) -> str:
    """格式化价格: $68,694.10 或 $0.6491"""
    if val is None:
        return "N/A"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    if abs(v) >= 1000:
        return f"${v:,.2f}"
    elif abs(v) >= 1:
        return f"${v:.2f}"
    else:
        return f"${v:.4f}"


def _fmt_change(val: Any) -> str:
    """格式化涨跌幅: +6.52% 或 -0.25%"""
    if val is None:
        return "N/A"
    v, _ = _parse_change(val)
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _safe_get(data: Any, *keys, default=None):
    """安全地从嵌套 dict/list 中获取值"""
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, default)
        elif isinstance(current, (list, tuple)) and isinstance(k, int):
            current = current[k] if 0 <= k < len(current) else default
        else:
            return default
        if current is default:
            return default
    return current


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


def _get_css() -> str:
    """返回完整的 CSS 样式字符串"""
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
        background: #0f0f1a;
        color: #e0e0e0;
        line-height: 1.6;
        padding: 20px;
        min-height: 100vh;
    }

    .container {
        max-width: 1200px;
        margin: 0 auto;
    }

    /* ---- Header ---- */
    .header {
        text-align: center;
        padding: 30px 0 20px;
        border-bottom: 1px solid #2a2a3e;
        margin-bottom: 30px;
    }
    .header h1 {
        font-size: 2.4em;
        font-weight: 700;
        background: linear-gradient(90deg, #42a5f5, #ab47bc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 8px;
    }
    .header .subtitle {
        color: #888;
        font-size: 0.95em;
    }
    .badges {
        display: flex;
        gap: 10px;
        justify-content: center;
        margin-top: 12px;
        flex-wrap: wrap;
    }
    .badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.82em;
        font-weight: 600;
    }
    .badge-red {
        background: rgba(239, 83, 80, 0.15);
        color: #ef5350;
        border: 1px solid rgba(239, 83, 80, 0.3);
    }
    .badge-green {
        background: rgba(38, 166, 154, 0.15);
        color: #26a69a;
        border: 1px solid rgba(38, 166, 154, 0.3);
    }
    .badge-orange {
        background: rgba(255, 167, 38, 0.15);
        color: #ffa726;
        border: 1px solid rgba(255, 167, 38, 0.3);
    }
    .badge-blue {
        background: rgba(66, 165, 245, 0.15);
        color: #42a5f5;
        border: 1px solid rgba(66, 165, 245, 0.3);
    }
    .badge-purple {
        background: rgba(171, 71, 188, 0.15);
        color: #ab47bc;
        border: 1px solid rgba(171, 71, 188, 0.3);
    }

    /* ---- Section ---- */
    .section {
        background: #1a1a2e;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        border: 1px solid #2a2a3e;
    }
    .section-title {
        font-size: 1.25em;
        font-weight: 600;
        margin-bottom: 18px;
        color: #f0f0f0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .section-title .icon {
        font-size: 1.1em;
    }

    /* ---- Market Overview Cards ---- */
    .market-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }
    .market-card {
        background: #141428;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2a2a3e;
        transition: border-color 0.2s, transform 0.2s;
    }
    .market-card:hover {
        border-color: #42a5f5;
        transform: translateY(-2px);
    }
    .market-card .ticker {
        font-size: 0.85em;
        color: #888;
        font-weight: 500;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .market-card .name {
        font-size: 0.78em;
        color: #666;
        margin-bottom: 10px;
    }
    .market-card .price {
        font-size: 1.6em;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .market-card .change {
        font-size: 1.0em;
        font-weight: 600;
    }
    .up { color: #26a69a; }
    .down { color: #ef5350; }
    .neutral { color: #888; }

    /* ---- Detail Table ---- */
    .detail-table {
        width: 100%;
        border-collapse: collapse;
    }
    .detail-table th {
        text-align: left;
        padding: 10px 14px;
        color: #888;
        font-size: 0.82em;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #2a2a3e;
    }
    .detail-table td {
        padding: 12px 14px;
        border-bottom: 1px solid rgba(42, 42, 62, 0.5);
        font-size: 0.92em;
    }
    .detail-table tr:hover {
        background: rgba(66, 165, 245, 0.04);
    }
    .detail-table .price-col {
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }
    .detail-table .change-col {
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    /* ---- Sentiment Panel ---- */
    .sentiment-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }
    .sentiment-box {
        background: #141428;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2a2a3e;
    }
    .sentiment-box h3 {
        font-size: 1.0em;
        color: #ccc;
        margin-bottom: 14px;
    }
    .progress-bar-outer {
        background: #0f0f1a;
        border-radius: 8px;
        height: 24px;
        overflow: hidden;
        margin: 10px 0;
    }
    .progress-bar-inner {
        height: 100%;
        border-radius: 8px;
        transition: width 0.5s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.78em;
        font-weight: 700;
        color: #fff;
    }
    .progress-red { background: linear-gradient(90deg, #b71c1c, #ef5350); }
    .progress-orange { background: linear-gradient(90deg, #e65100, #ffa726); }
    .progress-green { background: linear-gradient(90deg, #2e7d32, #66bb6a); }
    .progress-teal { background: linear-gradient(90deg, #00695c, #26a69a); }

    .sentiment-label {
        font-size: 0.88em;
        color: #aaa;
        margin-top: 6px;
    }
    .sentiment-value {
        font-size: 2.2em;
        font-weight: 700;
        margin: 8px 0;
    }

    /* ---- BTC Metrics Grid ---- */
    .btc-signal-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
    }
    .btc-signal-header .signal-strength {
        font-size: 1.3em;
        font-weight: 700;
    }
    .btc-metrics-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
    }
    .btc-metric-card {
        background: #141428;
        border-radius: 10px;
        padding: 16px;
        border: 1px solid #2a2a3e;
        text-align: center;
    }
    .btc-metric-card .metric-label {
        font-size: 0.78em;
        color: #888;
        margin-bottom: 6px;
    }
    .btc-metric-card .metric-value {
        font-size: 1.25em;
        font-weight: 700;
    }
    .btc-metric-card .metric-status {
        font-size: 0.75em;
        margin-top: 4px;
        font-weight: 500;
    }

    /* ---- Analysis Blocks ---- */
    .analysis-block {
        background: #141428;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 14px;
        border: 1px solid #2a2a3e;
    }
    .analysis-block .label {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.78em;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .label-macro { background: rgba(66, 165, 245, 0.15); color: #42a5f5; }
    .label-crypto { background: rgba(171, 71, 188, 0.15); color: #ab47bc; }
    .label-action { background: rgba(255, 167, 38, 0.15); color: #ffa726; }
    .analysis-block .content {
        font-size: 0.92em;
        color: #ccc;
        line-height: 1.75;
    }
    .analysis-block .content ul {
        padding-left: 18px;
        margin-top: 8px;
    }
    .analysis-block .content li {
        margin-bottom: 6px;
    }
    .analysis-timestamp {
        text-align: right;
        font-size: 0.78em;
        color: #555;
        margin-top: 10px;
    }

    /* ---- Catalysts ---- */
    .catalyst-item {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 12px 0;
        border-bottom: 1px solid rgba(42, 42, 62, 0.5);
    }
    .catalyst-item:last-child {
        border-bottom: none;
    }
    .catalyst-tag {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.72em;
        font-weight: 600;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .catalyst-text {
        font-size: 0.9em;
        color: #ccc;
    }

    /* ---- News ---- */
    .news-item {
        background: #141428;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
        border: 1px solid #2a2a3e;
        transition: border-color 0.2s;
    }
    .news-item:hover {
        border-color: #42a5f5;
    }
    .news-item .news-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
    }
    .news-item .news-category {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.7em;
        font-weight: 600;
    }
    .news-item .news-title {
        font-size: 0.95em;
        font-weight: 600;
        color: #e0e0e0;
    }
    .news-item .news-summary {
        font-size: 0.85em;
        color: #999;
        margin-top: 4px;
    }
    .news-item .news-source {
        font-size: 0.75em;
        color: #555;
        margin-top: 6px;
    }

    /* ---- Footer ---- */
    .footer {
        text-align: center;
        padding: 30px 0 20px;
        border-top: 1px solid #2a2a3e;
        margin-top: 10px;
    }
    .footer .source {
        font-size: 0.82em;
        color: #555;
        margin-bottom: 6px;
    }
    .footer .disclaimer {
        font-size: 0.75em;
        color: #444;
    }

    /* ---- Responsive ---- */
    @media (max-width: 768px) {
        body { padding: 12px; }
        .market-grid { grid-template-columns: repeat(2, 1fr); }
        .btc-metrics-grid { grid-template-columns: repeat(2, 1fr); }
        .sentiment-grid { grid-template-columns: 1fr; }
        .header h1 { font-size: 1.8em; }
    }
    @media (max-width: 480px) {
        .market-grid { grid-template-columns: 1fr; }
        .btc-metrics-grid { grid-template-columns: 1fr; }
    }
    """


# ---------------------------------------------------------------------------
# HTML Builders
# ---------------------------------------------------------------------------

# Friendly display names for tickers
_TICKER_NAMES = {
    "VOO": "标普500 ETF",
    "QQQM": "纳指100 ETF",
    "VIX": "恐慌指数",
    "GOLD": "黄金期货",
    "GLD": "黄金 ETF",
    "BTC": "比特币",
    "ETH": "以太坊",
    "NVDA": "英伟达",
    "TSLA": "特斯拉",
    "GOOG": "谷歌",
    "GOOGL": "谷歌",
    "RKLB": "Rocket Lab",
    "CRCL": "Circle",
    "HOOD": "Robinhood",
    "AAPL": "苹果",
    "MSFT": "微软",
    "AMZN": "亚马逊",
    "META": "Meta",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",
    "XAUT": "黄金代币",
    "HYPE": "Hyperliquid",
    "VIRTUAL": "Virtuals Protocol",
    "SOL": "Solana",
    "XRP": "瑞波币",
    "BNB": "币安币",
    "DOGE": "狗狗币",
    "ADA": "Cardano",
}


def _build_header(market_data: Dict) -> str:
    """构建页头: 标题、日期、状态徽章"""
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    # Use API timestamp if available
    api_ts = _safe_get(market_data, "timestamp", default=None)
    if api_ts:
        # Format: "2026-02-26T09:00:52.539Z"
        try:
            ts_str = str(api_ts).replace("Z", "+00:00")
            time_str = ts_str[:16].replace("T", " ") + " UTC"
        except Exception:
            pass

    # --- status badges ---
    badges_html = ""
    sentiment = _safe_get(market_data, "sentiment", default={})

    # 加密恐慌贪婪指数 (API returns flat: cryptoFearGreed=10)
    fear_val = (_safe_get(sentiment, "cryptoFearGreed", default=None)
                or _safe_get(sentiment, "fearGreedIndex", default=None))
    if fear_val is not None:
        try:
            fv = int(fear_val)
            if fv <= 20:
                badges_html += '<span class="badge badge-red">加密极度恐慌</span>'
            elif fv <= 35:
                badges_html += '<span class="badge badge-orange">加密恐慌</span>'
            elif fv >= 75:
                badges_html += '<span class="badge badge-green">加密极度贪婪</span>'
        except (TypeError, ValueError):
            pass

    # 黄金走强判断 (indices key is lowercase "gold")
    gold_change = _find_asset_change(market_data, "GOLD")
    if gold_change is not None:
        gc, _ = _parse_change(gold_change)
        if gc > 2.0:
            badges_html += '<span class="badge badge-orange">黄金走强</span>'

    # VIX 高波动 (indices key is lowercase "vix")
    vix_val = _find_asset_price(market_data, "VIX")
    if vix_val is not None:
        try:
            if float(vix_val) > 25:
                badges_html += '<span class="badge badge-red">高波动警报</span>'
        except (TypeError, ValueError):
            pass

    # CNN 恐慌贪婪
    cnn_fg = _safe_get(sentiment, "cnnFearGreed", default=None)
    cnn_label = _safe_get(sentiment, "cnnFearGreedLabel", default=None)
    if cnn_fg is not None:
        badges_html += f'<span class="badge badge-blue">CNN F&G: {cnn_fg} ({cnn_label or ""})</span>'

    return f"""
    <div class="header">
        <h1>大盘数据</h1>
        <div class="subtitle">{date_str} &nbsp;|&nbsp; 更新于 {time_str}</div>
        <div class="badges">{badges_html}</div>
    </div>
    """


def _iter_section(market_data: Dict, section_key: str):
    """迭代 market_data 中某个 section，兼容 dict-keyed 和 list 两种结构。

    API 实际返回 dict 结构，如 {"stocks": {"VOO": {...}, "NVDA": {...}}}
    同时兼容 list 结构，如 {"stocks": [{"ticker": "VOO", ...}]}

    Yields: (ticker_str, item_dict)
    """
    section = _safe_get(market_data, section_key, default=None)
    if section is None:
        return
    if isinstance(section, dict):
        for key, val in section.items():
            if isinstance(val, dict):
                yield key.upper(), val
            # else: skip non-dict values in section
    elif isinstance(section, (list, tuple)):
        for item in section:
            if isinstance(item, dict):
                t = (_safe_get(item, "ticker", default="")
                     or _safe_get(item, "symbol", default=""))
                yield t.upper(), item


def _find_asset_price(market_data: Dict, ticker: str) -> Any:
    """从 market_data 中查找某资产的价格（兼容 dict/list 结构）"""
    t_upper = ticker.upper()
    for section_key in ("stocks", "crypto", "indices"):
        for t, item in _iter_section(market_data, section_key):
            if t == t_upper:
                return _safe_get(item, "price", default=None)
    return None


def _find_asset_change(market_data: Dict, ticker: str) -> Any:
    """从 market_data 中查找某资产的涨跌幅"""
    t_upper = ticker.upper()
    for section_key in ("stocks", "crypto", "indices"):
        for t, item in _iter_section(market_data, section_key):
            if t == t_upper:
                return (_safe_get(item, "changePercent", default=None)
                        or _safe_get(item, "change24h", default=None)
                        or _safe_get(item, "change24hPercent", default=None)
                        or _safe_get(item, "change", default=None))
    return None


def _find_asset(market_data: Dict, ticker: str) -> Dict:
    """从 market_data 中查找某资产的完整 dict"""
    t_upper = ticker.upper()
    for section_key in ("stocks", "crypto", "indices"):
        for t, item in _iter_section(market_data, section_key):
            if t == t_upper:
                return item
    return {}


def _build_market_overview(market_data: Dict) -> str:
    """构建大盘概览: 6 张卡片 (VOO, QQQM, VIX, Gold, BTC, ETH)"""
    cards = []
    # indices key is lowercase in API ("vix", "gold"), _iter_section uppercases them
    overview_list = ["VOO", "QQQM", "VIX", "GOLD", "BTC", "ETH"]

    for ticker in overview_list:
        asset = _find_asset(market_data, ticker)
        price_raw = _safe_get(asset, "price", default=None)
        change_raw = (_safe_get(asset, "changePercent", default=None)
                      or _safe_get(asset, "change24h", default=None)
                      or _safe_get(asset, "change", default=None))

        price_str = _fmt_price(price_raw)
        change_str = _fmt_change(change_raw)
        _, css_cls = _parse_change(change_raw)
        name = _TICKER_NAMES.get(ticker, ticker)

        cards.append(f"""
        <div class="market-card">
            <div class="ticker">{ticker}</div>
            <div class="name">{name}</div>
            <div class="price {css_cls}">{price_str}</div>
            <div class="change {css_cls}">{change_str}</div>
        </div>
        """)

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">📊</span> 大盘概览</div>
        <div class="market-grid">
            {''.join(cards)}
        </div>
    </div>
    """


def _build_detail_table(market_data: Dict) -> str:
    """构建详细数据表: 除了概览卡片之外的股票和加密货币"""
    rows = []

    # Stocks (dict-keyed: {"VOO": {...}, "NVDA": {...}})
    for ticker, item in _iter_section(market_data, "stocks"):
        if ticker in OVERVIEW_TICKERS:
            continue
        price_raw = _safe_get(item, "price", default=None)
        change_raw = (_safe_get(item, "changePercent", default=None)
                      or _safe_get(item, "change", default=None))
        name = _TICKER_NAMES.get(ticker, ticker)
        _, css_cls = _parse_change(change_raw)
        rows.append(f"""
        <tr>
            <td>{ticker}</td>
            <td>{name}</td>
            <td class="price-col">{_fmt_price(price_raw)}</td>
            <td class="change-col {css_cls}">{_fmt_change(change_raw)}</td>
        </tr>
        """)

    # Crypto (dict-keyed: {"BTC": {...}, "ETH": {...}})
    for symbol, item in _iter_section(market_data, "crypto"):
        if symbol in OVERVIEW_TICKERS:
            continue
        price_raw = _safe_get(item, "price", default=None)
        change_raw = (_safe_get(item, "change24h", default=None)
                      or _safe_get(item, "changePercent", default=None)
                      or _safe_get(item, "change", default=None))
        name = _TICKER_NAMES.get(symbol, symbol)
        _, css_cls = _parse_change(change_raw)
        rows.append(f"""
        <tr>
            <td>{symbol}</td>
            <td>{name}</td>
            <td class="price-col">{_fmt_price(price_raw)}</td>
            <td class="change-col {css_cls}">{_fmt_change(change_raw)}</td>
        </tr>
        """)

    if not rows:
        return ""

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">📋</span> 详细数据</div>
        <table class="detail-table">
            <thead>
                <tr>
                    <th>代码</th>
                    <th>名称</th>
                    <th>价格</th>
                    <th>涨跌幅</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """


def _build_sentiment(market_data: Dict) -> str:
    """构建情绪面板: 加密恐慌贪婪指数 + CNN 恐慌贪婪指数

    API 返回 flat keys: cryptoFearGreed=10, cryptoFearGreedLabel="Extreme Fear",
    cnnFearGreed=46, cnnFearGreedLabel="neutral"
    """
    sentiment = _safe_get(market_data, "sentiment", default={})

    # --- 加密恐慌贪婪指数 ---
    crypto_fg = _safe_get(sentiment, "cryptoFearGreed", default=50)
    crypto_fg_label = _safe_get(sentiment, "cryptoFearGreedLabel", default="N/A")
    crypto_fg_prev = _safe_get(sentiment, "cryptoFearGreedPrev", default=None)
    crypto_fg_change = _safe_get(sentiment, "cryptoFearGreedChange", default=None)

    try:
        fg_int = int(crypto_fg)
    except (TypeError, ValueError):
        fg_int = 50

    # Progress bar color
    if fg_int <= 25:
        bar_cls = "progress-red"
    elif fg_int <= 50:
        bar_cls = "progress-orange"
    elif fg_int <= 75:
        bar_cls = "progress-green"
    else:
        bar_cls = "progress-teal"

    fg_color_style = ""
    if fg_int <= 25:
        fg_color_style = "color: #ef5350;"
    elif fg_int <= 50:
        fg_color_style = "color: #ffa726;"
    else:
        fg_color_style = "color: #26a69a;"

    # Previous value note
    prev_html = ""
    if crypto_fg_prev is not None:
        prev_html = f'<div class="sentiment-label">前值: {crypto_fg_prev}</div>'

    # --- CNN Fear & Greed (flat: cnnFearGreed=46, cnnFearGreedLabel="neutral") ---
    cnn_fg_val = _safe_get(sentiment, "cnnFearGreed", default=None)
    cnn_fg_label = _safe_get(sentiment, "cnnFearGreedLabel", default="")

    cnn_fg_int = 50
    if cnn_fg_val is not None:
        try:
            cnn_fg_int = int(cnn_fg_val)
        except (TypeError, ValueError):
            cnn_fg_int = 50

    cnn_color_style = ""
    if cnn_fg_int <= 25:
        cnn_color_style = "color: #ef5350;"
        cnn_bar_cls = "progress-red"
    elif cnn_fg_int <= 50:
        cnn_color_style = "color: #ffa726;"
        cnn_bar_cls = "progress-orange"
    elif cnn_fg_int <= 75:
        cnn_color_style = "color: #26a69a;"
        cnn_bar_cls = "progress-green"
    else:
        cnn_color_style = "color: #26a69a;"
        cnn_bar_cls = "progress-teal"

    cnn_box_html = ""
    if cnn_fg_val is not None:
        cnn_box_html = f"""
            <div class="sentiment-box">
                <h3>CNN 恐慌贪婪指数</h3>
                <div class="sentiment-value" style="{cnn_color_style}">{cnn_fg_int}</div>
                <div class="sentiment-label">{cnn_fg_label}</div>
                <div class="progress-bar-outer">
                    <div class="progress-bar-inner {cnn_bar_cls}" style="width: {cnn_fg_int}%;">{cnn_fg_int}</div>
                </div>
            </div>
        """

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🧠</span> 市场情绪</div>
        <div class="sentiment-grid">
            <div class="sentiment-box">
                <h3>加密恐慌贪婪指数</h3>
                <div class="sentiment-value" style="{fg_color_style}">{fg_int}</div>
                <div class="sentiment-label">{crypto_fg_label}</div>
                <div class="progress-bar-outer">
                    <div class="progress-bar-inner {bar_cls}" style="width: {fg_int}%;">{fg_int}</div>
                </div>
                {prev_html}
            </div>
            {cnn_box_html}
        </div>
    </div>
    """


def _build_btc_signal(market_data: Dict) -> str:
    """构建 BTC 信号面板: 6 个指标卡片

    API 返回 flat btcMetrics: weeklyRsi=25, volume24h=229471784,
    volumeChangePercent=-67, sthSopr=0.963, lthSopr=1.063,
    lthSupplyPercent=72.7, wma200Price=58316, wma200Multiplier=1.1
    """
    btc_data = (_safe_get(market_data, "btcMetrics", default=None)
                or _safe_get(market_data, "btc_metrics", default=None)
                or {})
    if not btc_data:
        return ""

    # Derive signal from metrics
    weekly_rsi = _safe_get(btc_data, "weeklyRsi", default=None)
    sth_sopr = _safe_get(btc_data, "sthSopr", default=None)
    vol_change = _safe_get(btc_data, "volumeChangePercent", default=None)

    # Determine overall signal
    bullish_count = 0
    bearish_count = 0
    if weekly_rsi is not None:
        if weekly_rsi < 30:
            bullish_count += 1  # oversold = potential upside
        elif weekly_rsi > 70:
            bearish_count += 1
    if sth_sopr is not None:
        if sth_sopr < 1.0:
            bearish_count += 1  # short-term holders at a loss
        else:
            bullish_count += 1
    if vol_change is not None:
        if vol_change < -50:
            bearish_count += 1  # low volume

    if bullish_count > bearish_count:
        signal_text = "偏多"
        sig_color = "#26a69a"
    elif bearish_count > bullish_count:
        signal_text = "偏空"
        sig_color = "#ef5350"
    else:
        signal_text = "中性"
        sig_color = "#ffa726"

    # Build 6 metric cards with interpreted status
    def _fmt_volume(v):
        if v is None:
            return "--"
        try:
            fv = float(v)
            if fv >= 1e9:
                return f"${fv / 1e9:.1f}B"
            elif fv >= 1e6:
                return f"${fv / 1e6:.0f}M"
            else:
                return f"${fv:,.0f}"
        except (TypeError, ValueError):
            return str(v)

    metrics = [
        {
            "label": "周线RSI",
            "value": str(weekly_rsi) if weekly_rsi is not None else "--",
            "status": "超卖区" if weekly_rsi is not None and weekly_rsi < 30 else
                      "超买区" if weekly_rsi is not None and weekly_rsi > 70 else
                      "中性区" if weekly_rsi is not None else "",
            "color": "#26a69a" if weekly_rsi is not None and weekly_rsi < 30 else
                     "#ef5350" if weekly_rsi is not None and weekly_rsi > 70 else "#888",
        },
        {
            "label": "24h成交量",
            "value": _fmt_volume(_safe_get(btc_data, "volume24h", default=None)),
            "status": f"较均值 {vol_change}%" if vol_change is not None else "",
            "color": "#ef5350" if vol_change is not None and vol_change < -30 else
                     "#26a69a" if vol_change is not None and vol_change > 30 else "#888",
        },
        {
            "label": "STH-SOPR",
            "value": str(sth_sopr) if sth_sopr is not None else "--",
            "status": "亏损出售" if sth_sopr is not None and sth_sopr < 1.0 else
                      "盈利出售" if sth_sopr is not None else "",
            "color": "#ef5350" if sth_sopr is not None and sth_sopr < 1.0 else "#26a69a",
        },
        {
            "label": "LTH-SOPR",
            "value": str(_safe_get(btc_data, "lthSopr", default="--")),
            "status": "盈利出售" if _safe_get(btc_data, "lthSopr", default=1) >= 1.0 else "亏损出售",
            "color": "#26a69a" if _safe_get(btc_data, "lthSopr", default=1) >= 1.0 else "#ef5350",
        },
        {
            "label": "长期供应占比",
            "value": f"{_safe_get(btc_data, 'lthSupplyPercent', default='--')}%",
            "status": "健康" if _safe_get(btc_data, "lthSupplyPercent", default=0) > 65 else "偏低",
            "color": "#26a69a" if _safe_get(btc_data, "lthSupplyPercent", default=0) > 65 else "#ffa726",
        },
        {
            "label": "200周均线",
            "value": f"${_safe_get(btc_data, 'wma200Price', default='--'):,}" if isinstance(_safe_get(btc_data, 'wma200Price', default='--'), (int, float)) else str(_safe_get(btc_data, 'wma200Price', default='--')),
            "status": f"倍数: {_safe_get(btc_data, 'wma200Multiplier', default='--')}x",
            "color": "#26a69a" if isinstance(_safe_get(btc_data, "wma200Multiplier", default=1), (int, float)) and _safe_get(btc_data, "wma200Multiplier", default=1) > 1 else "#ffa726",
        },
    ]

    cards_html = []
    for m in metrics:
        cards_html.append(f"""
        <div class="btc-metric-card">
            <div class="metric-label">{m['label']}</div>
            <div class="metric-value">{m['value']}</div>
            <div class="metric-status" style="color: {m['color']};">{m['status']}</div>
        </div>
        """)

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">&#8383;</span> BTC 链上信号</div>
        <div class="btc-signal-header">
            <div class="signal-strength" style="color: {sig_color};">综合信号: {signal_text}</div>
        </div>
        <div class="btc-metrics-grid">
            {''.join(cards_html)}
        </div>
    </div>
    """


def _build_analysis(analysis_data: Dict) -> str:
    """构建分析板块: 宏观/加密/操作建议"""
    blocks = []

    # 宏观分析
    macro = (_safe_get(analysis_data, "macroAnalysis", default=None)
             or _safe_get(analysis_data, "macro_analysis", default=None)
             or _safe_get(analysis_data, "macro", default=None))
    if macro:
        content = macro if isinstance(macro, str) else _safe_get(macro, "content", default=str(macro))
        blocks.append(f"""
        <div class="analysis-block">
            <div class="label label-macro">宏观分析</div>
            <div class="content">{_format_analysis_text(content)}</div>
        </div>
        """)

    # 加密分析
    crypto = (_safe_get(analysis_data, "cryptoAnalysis", default=None)
              or _safe_get(analysis_data, "crypto_analysis", default=None)
              or _safe_get(analysis_data, "crypto", default=None))
    if crypto:
        content = crypto if isinstance(crypto, str) else _safe_get(crypto, "content", default=str(crypto))
        blocks.append(f"""
        <div class="analysis-block">
            <div class="label label-crypto">加密分析</div>
            <div class="content">{_format_analysis_text(content)}</div>
        </div>
        """)

    # 操作建议 (API key: actionSuggestions)
    actions = (_safe_get(analysis_data, "actionSuggestions", default=None)
               or _safe_get(analysis_data, "actionItems", default=None)
               or _safe_get(analysis_data, "action_items", default=None)
               or _safe_get(analysis_data, "actions", default=None))
    if actions:
        if isinstance(actions, list):
            li_items = "".join(f"<li>{item}</li>" for item in actions)
            content = f"<ul>{li_items}</ul>"
        elif isinstance(actions, str):
            content = _format_analysis_text(actions)
        else:
            content = _format_analysis_text(str(actions))
        blocks.append(f"""
        <div class="analysis-block">
            <div class="label label-action">操作建议</div>
            <div class="content">{content}</div>
        </div>
        """)

    if not blocks:
        return ""

    # Timestamp
    ts = (_safe_get(analysis_data, "generatedAt", default=None)
          or _safe_get(analysis_data, "generated_at", default=None)
          or _safe_get(analysis_data, "timestamp", default=None))
    ts_html = ""
    if ts:
        ts_html = f'<div class="analysis-timestamp">AI 生成于: {ts}</div>'

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🔍</span> 市场分析</div>
        {''.join(blocks)}
        {ts_html}
    </div>
    """


def _format_analysis_text(text: str) -> str:
    """将分析文本格式化为 HTML（处理换行和列表）"""
    if not text:
        return ""
    # Escape basic HTML
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert markdown-style lists
    lines = text.split("\n")
    result = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                result.append("<ul>")
                in_list = True
            result.append(f"<li>{stripped[2:]}</li>")
        else:
            if in_list:
                result.append("</ul>")
                in_list = False
            if stripped:
                result.append(f"<p>{stripped}</p>")
    if in_list:
        result.append("</ul>")
    return "\n".join(result)


def _build_catalysts(analysis_data: Dict) -> str:
    """构建催化剂列表"""
    catalysts = (_safe_get(analysis_data, "catalysts", default=None)
                 or _safe_get(analysis_data, "upcoming_catalysts", default=None)
                 or _safe_get(analysis_data, "upcomingCatalysts", default=[]))
    if not catalysts:
        return ""

    items = []
    for cat in catalysts:
        if isinstance(cat, str):
            text = cat
            tag = "Event"
            tag_color = "#42a5f5"
        elif isinstance(cat, dict):
            text = (_safe_get(cat, "text", default=None)
                    or _safe_get(cat, "description", default=None)
                    or _safe_get(cat, "title", default=str(cat)))
            tag = (_safe_get(cat, "category", default=None)
                   or _safe_get(cat, "tag", default=None)
                   or _safe_get(cat, "type", default="Event"))
            tag_color = NEWS_CATEGORY_COLORS.get(tag, "#42a5f5")
        else:
            continue

        items.append(f"""
        <div class="catalyst-item">
            <span class="catalyst-tag" style="background: {tag_color}22; color: {tag_color}; border: 1px solid {tag_color}44;">{tag}</span>
            <span class="catalyst-text">{text}</span>
        </div>
        """)

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">🗓️</span> 即将到来的催化剂</div>
        {''.join(items)}
    </div>
    """


def _build_news(analysis_data: Dict) -> str:
    """构建新闻列表: 最多显示 10 条

    API key: topNews, each item has title/tag/summary/action/source/url
    """
    news_list = (_safe_get(analysis_data, "topNews", default=None)
                 or _safe_get(analysis_data, "news", default=None)
                 or _safe_get(analysis_data, "top_news", default=[]))
    if not news_list:
        return ""

    items = []
    for news in news_list[:10]:
        if isinstance(news, str):
            title = news
            summary = ""
            category = "News"
            source = ""
            action = ""
            url = ""
        elif isinstance(news, dict):
            title = (_safe_get(news, "title", default=None)
                     or _safe_get(news, "headline", default=""))
            summary = (_safe_get(news, "summary", default=None)
                       or _safe_get(news, "description", default=""))
            category = (_safe_get(news, "tag", default=None)
                        or _safe_get(news, "category", default=None)
                        or _safe_get(news, "type", default="News"))
            source = (_safe_get(news, "source", default=None)
                      or _safe_get(news, "publisher", default=""))
            action = _safe_get(news, "action", default="")
            url = _safe_get(news, "url", default="")
        else:
            continue

        cat_color = NEWS_CATEGORY_COLORS.get(category, "#42a5f5")
        summary_html = f'<div class="news-summary">{summary}</div>' if summary else ""
        action_html = f'<div class="news-summary" style="color: #ab47bc; margin-top: 4px;">&#9654; {action}</div>' if action else ""
        source_html = f'<div class="news-source">{source}</div>' if source else ""

        # Make title a link if URL exists
        if url:
            title_html = f'<a href="{url}" target="_blank" style="color: #e0e0e0; text-decoration: none;" class="news-title">{title}</a>'
        else:
            title_html = f'<span class="news-title">{title}</span>'

        items.append(f"""
        <div class="news-item">
            <div class="news-header">
                <span class="news-category" style="background: {cat_color}22; color: {cat_color};">{category}</span>
                {title_html}
            </div>
            {summary_html}
            {action_html}
            {source_html}
        </div>
        """)

    return f"""
    <div class="section">
        <div class="section-title"><span class="icon">📰</span> 重要新闻</div>
        {''.join(items)}
    </div>
    """


def _build_footer() -> str:
    """构建页脚: 免责声明"""
    return """
    <div class="footer">
        <div class="disclaimer">
            本页面内容由 AI 自动生成，仅供参考，不构成投资建议。
            市场有风险，投资需谨慎。请结合个人实际情况做出决策。
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Embeddable content (for integration into stock report tabs)
# ---------------------------------------------------------------------------


def _get_scoped_css(scope: str = ".md-panel") -> str:
    """返回带作用域前缀的 CSS，避免和宿主页面样式冲突。

    将原始 CSS 的每条规则都加上 ``scope`` 前缀，例如:
        .section { ... }  →  .md-panel .section { ... }
    同时去掉 body/* 等全局重置，由宿主页面负责。
    """
    import re

    raw = _get_css()

    # 去掉 * { ... } 和 body { ... } 全局重置
    raw = re.sub(r'\*\s*\{[^}]*\}', '', raw)
    raw = re.sub(r'body\s*\{[^}]*\}', '', raw)

    lines = raw.split('\n')
    result = []
    in_media = False

    for line in lines:
        stripped = line.strip()

        # @media 行保留原样
        if stripped.startswith('@media'):
            in_media = True
            result.append(line)
            continue

        # @media 结尾
        if in_media and stripped == '}':
            # 判断是否是 @media 的结尾（不是规则的 }）
            # 简单处理：如果缩进 <= 4 个空格 或者行首就是 }，认为是 @media 结尾
            if len(line) - len(line.lstrip()) <= 4:
                in_media = False
                result.append(line)
                continue

        # 选择器行: 包含 { 且不以 } 结尾的纯 } 行
        if '{' in stripped and not stripped.startswith('}') and not stripped.startswith('@') and not stripped.startswith('/*'):
            # 可能有多选择器 (a, b { ... })
            selector_part, brace_rest = stripped.split('{', 1)
            selectors = [s.strip() for s in selector_part.split(',')]
            scoped = ', '.join(f'{scope} {s}' for s in selectors if s)
            result.append(f'    {scoped} {{{brace_rest}')
        else:
            result.append(line)

    return '\n'.join(result)


def build_dashboard_content() -> Dict[str, str]:
    """获取大盘数据，返回可嵌入 HTML 片段 + 对应 CSS。

    Returns:
        {"html": str, "css": str}
        - html: 带 class="md-panel" 的 div 包裹的完整大盘内容
        - css: 以 .md-panel 为作用域的全部样式

    API 获取失败时返回降级提示 HTML。
    """
    try:
        data = fetch_all_data()
        market_data = data.get("market", {})
        analysis_data = data.get("analysis", {})

        if not market_data:
            raise RuntimeError("market-data 返回为空")

        parts = [
            _build_header(market_data),
            _build_market_overview(market_data),
            _build_detail_table(market_data),
            _build_sentiment(market_data),
            _build_btc_signal(market_data),
            _build_analysis(analysis_data),
            _build_catalysts(analysis_data),
            _build_news(analysis_data),
            _build_footer(),
        ]
        inner_html = "\n".join(parts)
    except Exception as e:
        inner_html = f"""
        <div style="text-align:center;padding:60px 20px;color:#888;">
            <div style="font-size:2em;margin-bottom:16px;">📡</div>
            <div style="font-size:1.1em;margin-bottom:8px;">暂时无法获取大盘数据</div>
            <div style="font-size:0.85em;color:#555;">{str(e)}</div>
        </div>"""

    html = f'<div class="md-panel">\n{inner_html}\n</div>'
    css = _get_scoped_css(".md-panel")
    # 与股票分析 .container 保持一致的居中布局
    css += "\n.md-panel { max-width: 1100px; margin: 0 auto; padding: 20px; }"

    return {"html": html, "css": css}


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def generate_market_dashboard() -> str:
    """获取数据 → 组装完整 HTML → 保存到文件 → 自动打开浏览器。

    Returns:
        保存的文件路径
    """
    print("[market_dashboard] 正在获取市场数据...")
    data = fetch_all_data()
    market_data = data.get("market", {})
    analysis_data = data.get("analysis", {})

    print(f"[market_dashboard] market keys: {list(market_data.keys())}")
    print(f"[market_dashboard] analysis keys: {list(analysis_data.keys())}")

    # Assemble HTML
    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>大盘数据 Dashboard</title>",
        "<style>",
        _get_css(),
        "</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        _build_header(market_data),
        _build_market_overview(market_data),
        _build_detail_table(market_data),
        _build_sentiment(market_data),
        _build_btc_signal(market_data),
        _build_analysis(analysis_data),
        _build_catalysts(analysis_data),
        _build_news(analysis_data),
        _build_footer(),
        "</div>",
        "</body>",
        "</html>",
    ]
    full_html = "\n".join(html_parts)

    # Ensure output directory exists
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

    # Save file
    date_stamp = datetime.now().strftime("%Y%m%d")
    filename = f"market_dashboard_{date_stamp}.html"
    filepath = os.path.join(DEFAULT_OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"[market_dashboard] Dashboard 已保存到: {filepath}")

    # Auto-open in browser on macOS
    try:
        subprocess.run(["open", filepath], check=False)
    except FileNotFoundError:
        print("[market_dashboard] 无法自动打开浏览器（非 macOS?），请手动打开文件")

    return filepath


if __name__ == "__main__":
    path = generate_market_dashboard()
    print(f"\nDone! File: {path}")
