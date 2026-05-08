"""
Polymarket 看盘、标的发现与深度分析 v0.2

功能:
- list_trending_markets — 按 24h 成交量排序的热门活跃市场
- list_new_markets      — 最近 N 天新上线的市场
- list_by_category      — 按分类(tag)拉市场，比如 "politics" / "crypto" / "sports"
- list_categories       — 列出常见分类(从热门 events 聚合)
- search_markets        — 关键词搜索市场（标题模糊匹配）
- analyze_market_depth  — 单市场深度分析（历史价格 + 大户持仓 + 最近成交 + 信号）

数据源 (公开，无需 auth):
- https://gamma-api.polymarket.com/markets   — 市场元数据
- https://gamma-api.polymarket.com/events    — 事件(含 tags 分类)
- https://clob.polymarket.com/prices-history — 历史价格曲线
- https://data-api.polymarket.com/holders    — 大户持仓
- https://data-api.polymarket.com/trades     — 实时成交

仅使用 Python 标准库。
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
DATA_BASE = "https://data-api.polymarket.com"
DEFAULT_TIMEOUT = 15
USER_AGENT = "stock-master/polymarket-0.2"


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------


def _fetch(base: str, path: str, params: Optional[Dict[str, Any]] = None,
           timeout: int = DEFAULT_TIMEOUT) -> Any:
    """GET {base}{path}?{params}, return parsed JSON or None on failure."""
    url = f"{base}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, OSError) as exc:
        print(f"[polymarket] fetch failed ({path}): {exc}")
        return None


def _gamma(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    return _fetch(GAMMA_BASE, path, params)


def _clob(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    return _fetch(CLOB_BASE, path, params)


def _data(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    return _fetch(DATA_BASE, path, params)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_outcomes(market: Dict[str, Any]) -> Dict[str, float]:
    """outcomes/outcomePrices 是 JSON 字符串，解析为 {outcome: price} dict。"""
    out: Dict[str, float] = {}
    raw_names = market.get("outcomes")
    raw_prices = market.get("outcomePrices")
    try:
        names = json.loads(raw_names) if isinstance(raw_names, str) else raw_names or []
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices or []
    except json.JSONDecodeError:
        return out
    for n, p in zip(names, prices):
        try:
            out[str(n)] = float(p)
        except (TypeError, ValueError):
            continue
    return out


def _parse_token_ids(market: Dict[str, Any]) -> List[str]:
    """clobTokenIds 是 JSON 字符串，解析为 [yes_token, no_token]。"""
    raw = market.get("clobTokenIds")
    if not raw:
        return []
    try:
        ids = json.loads(raw) if isinstance(raw, str) else raw
        return [str(x) for x in ids]
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _delta_days(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _condense(market: Dict[str, Any]) -> Dict[str, Any]:
    """提取核心字段，扔掉无关字段，便于消费。"""
    outcomes = _parse_outcomes(market)
    end_dt = _parse_dt(market.get("endDate"))
    created_dt = _parse_dt(market.get("createdAt"))
    # groupItemTitle 通常包含 question 实际赌的日期（"December 31, 2026"）
    # 比 endDate (trading 截止) 更可靠
    group_item = market.get("groupItemTitle") or ""
    return {
        "id": market.get("id"),
        "slug": market.get("slug"),
        "condition_id": market.get("conditionId"),
        "question": market.get("question"),
        "group_item_title": group_item,
        "outcomes": outcomes,
        "token_ids": _parse_token_ids(market),
        "best_bid": market.get("bestBid"),
        "best_ask": market.get("bestAsk"),
        "spread": market.get("spread"),
        "last_trade_price": market.get("lastTradePrice"),
        "volume_24h": _safe_float(market.get("volume24hr")),
        "volume_total": _safe_float(market.get("volume")),
        "liquidity": _safe_float(market.get("liquidity")),
        # endDate = trading 截止时间（market 不再接受新订单的时间），
        # 不一定是 question 里赌的日期。提前结算的市场，trading
        # 在结果出来时就停。所以下方 days_until_end 仅作流动性参考，
        # 不能用作"距 question 答案揭晓的天数"。
        "trading_end_date": end_dt.isoformat() if end_dt else None,
        "created_at": created_dt.isoformat() if created_dt else None,
        "days_until_trading_end": (-_delta_days(end_dt)) if end_dt else None,
        "days_since_created": _delta_days(created_dt),
        "active": market.get("active"),
        "closed": market.get("closed"),
        "accepting_orders": market.get("acceptingOrders"),
        "url": f"https://polymarket.com/market/{market.get('slug')}" if market.get("slug") else None,
        "image": market.get("image"),
        # 兼容字段（旧名）
        "end_date": end_dt.isoformat() if end_dt else None,
        "days_until_end": (-_delta_days(end_dt)) if end_dt else None,
    }


# ---------------------------------------------------------------------------
# 1) Trending / New / Search
# ---------------------------------------------------------------------------


def list_trending_markets(limit: int = 20,
                          min_liquidity: float = 1000.0) -> List[Dict[str, Any]]:
    """按 24h 成交量降序的热门活跃市场。"""
    raw = _gamma("/markets", {
        "active": "true",
        "closed": "false",
        "limit": limit * 3,
        "order": "volume24hr",
        "ascending": "false",
    })
    if not isinstance(raw, list):
        return []
    out = []
    for m in raw:
        c = _condense(m)
        if c["liquidity"] < min_liquidity:
            continue
        if not c["accepting_orders"]:
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def list_new_markets(days: int = 7, limit: int = 20,
                     min_liquidity: float = 500.0) -> List[Dict[str, Any]]:
    """最近 N 天新上线的活跃市场，按创建时间降序。"""
    raw = _gamma("/markets", {
        "active": "true",
        "closed": "false",
        "limit": 200,
        "order": "createdAt",
        "ascending": "false",
    })
    if not isinstance(raw, list):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for m in raw:
        c = _condense(m)
        created = _parse_dt(m.get("createdAt"))
        if created is None or created < cutoff:
            continue
        if c["liquidity"] < min_liquidity:
            continue
        if not c["accepting_orders"]:
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def search_markets(keyword: str, limit: int = 20,
                   active_only: bool = True) -> List[Dict[str, Any]]:
    """关键词搜索市场（标题模糊匹配）。"""
    params = {
        "limit": 200,
        "order": "volume24hr",
        "ascending": "false",
    }
    if active_only:
        params["active"] = "true"
        params["closed"] = "false"
    raw = _gamma("/markets", params)
    if not isinstance(raw, list):
        return []
    kw = keyword.lower()
    out = []
    for m in raw:
        q = (m.get("question") or "").lower()
        slug = (m.get("slug") or "").lower()
        if kw in q or kw in slug:
            out.append(_condense(m))
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# 2) Categories (via events.tags)
# ---------------------------------------------------------------------------

# 用户友好的中文分类 → Polymarket tag slug 映射
# (Polymarket 没有顶级"分类"概念，标签很碎，这里收敛到最常用的几个)
CATEGORY_PRESETS = {
    "政治": ["politics", "trump", "biden", "elections", "us-politics"],
    "加密": ["crypto", "bitcoin", "ethereum", "memecoins"],
    "体育": ["sports", "nba", "nfl", "soccer", "football"],
    "地缘": ["geopolitics", "iran", "russia-ukraine", "china", "middle-east"],
    "科技": ["tech", "ai", "openai", "tesla"],
    "经济": ["fed", "economy", "inflation", "stocks"],
    "娱乐": ["entertainment", "culture", "movies", "tv"],
}


def list_by_category(category: str, limit: int = 20,
                     min_liquidity: float = 1000.0) -> List[Dict[str, Any]]:
    """
    按用户友好的分类拉市场。
    category 可以是中文(政治/加密/体育/地缘/科技/经济/娱乐) 或 Polymarket tag slug。
    通过 events 端点的 tag 过滤实现，再展开 events.markets。
    """
    # 解析分类 → tag slugs
    tag_slugs = CATEGORY_PRESETS.get(category, [category])

    seen_market_ids = set()
    out: List[Dict[str, Any]] = []

    for tag in tag_slugs:
        events = _gamma("/events", {
            "active": "true",
            "closed": "false",
            "limit": 50,
            "order": "volume24hr",
            "ascending": "false",
            "tag_slug": tag,
        })
        if not isinstance(events, list):
            continue
        for ev in events:
            for m in ev.get("markets", []) or []:
                mid = m.get("id")
                if mid in seen_market_ids:
                    continue
                seen_market_ids.add(mid)
                c = _condense(m)
                if c["liquidity"] < min_liquidity:
                    continue
                if not c["accepting_orders"]:
                    continue
                # 给市场加个事件上下文
                c["event_title"] = ev.get("title")
                c["event_slug"] = ev.get("slug")
                out.append(c)

    # 按 24h 成交量降序
    out.sort(key=lambda x: x["volume_24h"], reverse=True)
    return out[:limit]


def list_categories() -> List[str]:
    """返回支持的中文分类名。"""
    return list(CATEGORY_PRESETS.keys())


# ---------------------------------------------------------------------------
# 3) Single-market depth analysis
# ---------------------------------------------------------------------------


def fetch_market_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """通过 slug 拉单个市场的元数据。"""
    raw = _gamma("/markets", {"slug": slug, "limit": 1})
    if isinstance(raw, list) and raw:
        return raw[0]
    return None


def fetch_price_history(token_id: str, interval: str = "1m",
                        fidelity: int = 60) -> List[Dict[str, Any]]:
    """
    拉单个 outcome token 的历史价格曲线。
    interval: "1m" "1w" "1d" "6h" "1h" "max"
    fidelity: 数据点采样精度(分钟)
    返回 [{t: unix_ts, p: price}, ...]
    """
    raw = _clob("/prices-history", {
        "market": token_id,
        "interval": interval,
        "fidelity": fidelity,
    })
    if isinstance(raw, dict):
        return raw.get("history", []) or []
    return []


def fetch_holders(condition_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    拉某市场的大户持仓。
    返回 [{token, holders: [{proxyWallet, name, amount, outcomeIndex, ...}]}]
    通常返回 2 条(YES/NO 各一)，每条 holders 是该 outcome 的 top N 大户。
    """
    raw = _data("/holders", {"market": condition_id, "limit": limit})
    if isinstance(raw, list):
        return raw
    return []


def fetch_recent_trades(condition_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """拉最近的成交记录。"""
    raw = _data("/trades", {"market": condition_id, "limit": limit})
    if isinstance(raw, list):
        return raw
    return []


def _compute_signals(history: List[Dict[str, Any]],
                     trades: List[Dict[str, Any]],
                     holders_data: List[Dict[str, Any]],
                     market: Dict[str, Any]) -> Dict[str, Any]:
    """
    从原始数据计算简单信号。
    - 价格变化 (24h / 7d)
    - 波动率 (近期价格的标准差)
    - 大单成交方向 (BUY/SELL 比例 + YES/NO 资金流向)
    - 大户集中度 (top 5 占总持仓比)
    """
    signals: Dict[str, Any] = {}

    # 价格变化
    if history:
        latest_price = history[-1].get("p")
        latest_ts = history[-1].get("t", 0)
        signals["latest_price"] = latest_price

        # 24h 前的点
        ts_24h = latest_ts - 86400
        ts_7d = latest_ts - 86400 * 7
        price_24h_ago = None
        price_7d_ago = None
        for h in history:
            t = h.get("t", 0)
            if price_24h_ago is None and t >= ts_24h:
                price_24h_ago = h.get("p")
            if price_7d_ago is None and t >= ts_7d:
                price_7d_ago = h.get("p")
            if price_24h_ago is not None and price_7d_ago is not None:
                break

        if price_24h_ago and latest_price is not None:
            signals["price_change_24h"] = round(latest_price - price_24h_ago, 4)
            signals["price_change_24h_pct"] = round(
                (latest_price - price_24h_ago) / max(price_24h_ago, 0.001) * 100, 2
            )
        if price_7d_ago and latest_price is not None:
            signals["price_change_7d"] = round(latest_price - price_7d_ago, 4)
            signals["price_change_7d_pct"] = round(
                (latest_price - price_7d_ago) / max(price_7d_ago, 0.001) * 100, 2
            )

        # 波动率(近 100 个点的标准差)
        recent = [h.get("p") for h in history[-100:] if h.get("p") is not None]
        if len(recent) >= 5:
            mean = sum(recent) / len(recent)
            var = sum((p - mean) ** 2 for p in recent) / len(recent)
            signals["volatility"] = round(var ** 0.5, 4)

    # 大单成交方向
    if trades:
        buy_yes_size = 0.0
        buy_no_size = 0.0
        sell_yes_size = 0.0
        sell_no_size = 0.0
        for t in trades:
            size = _safe_float(t.get("size"))
            outcome = t.get("outcome", "")
            side = t.get("side", "")
            if outcome == "Yes" and side == "BUY":
                buy_yes_size += size
            elif outcome == "Yes" and side == "SELL":
                sell_yes_size += size
            elif outcome == "No" and side == "BUY":
                buy_no_size += size
            elif outcome == "No" and side == "SELL":
                sell_no_size += size

        net_yes = buy_yes_size - sell_yes_size
        net_no = buy_no_size - sell_no_size
        signals["recent_buy_yes_size"] = round(buy_yes_size, 2)
        signals["recent_buy_no_size"] = round(buy_no_size, 2)
        signals["recent_net_yes_flow"] = round(net_yes, 2)
        signals["recent_net_no_flow"] = round(net_no, 2)
        signals["trades_count"] = len(trades)

    # 大户集中度
    if holders_data:
        for token_data in holders_data:
            outcome_idx = None
            holders = token_data.get("holders", [])
            if holders:
                outcome_idx = holders[0].get("outcomeIndex")
            top5 = sum(_safe_float(h.get("amount")) for h in holders[:5])
            total = sum(_safe_float(h.get("amount")) for h in holders)
            if total > 0:
                concentration = round(top5 / total * 100, 1)
                key = f"holder_concentration_outcome_{outcome_idx}"
                signals[key] = concentration

    return signals


def _interpret_signals(signals: Dict[str, Any], market: Dict[str, Any]) -> List[str]:
    """把数值信号翻译成人话。"""
    interp: List[str] = []
    outcomes = _parse_outcomes(market)
    yes_p = outcomes.get("Yes")

    # 价格变化
    pc24 = signals.get("price_change_24h")
    pc24p = signals.get("price_change_24h_pct")
    if pc24 is not None and pc24p is not None:
        if abs(pc24) < 0.005:
            interp.append(f"📊 24h 价格基本持平 ({pc24:+.4f})")
        elif pc24 > 0:
            interp.append(f"📈 24h YES 概率上涨 {pc24p:+.1f}% (从 {yes_p - pc24:.3f} → {yes_p:.3f})")
        else:
            interp.append(f"📉 24h YES 概率下跌 {pc24p:+.1f}% (从 {yes_p - pc24:.3f} → {yes_p:.3f})")

    pc7d = signals.get("price_change_7d_pct")
    if pc7d is not None:
        if abs(pc7d) >= 10:
            arrow = "🚀" if pc7d > 0 else "💥"
            interp.append(f"{arrow} 7天累计变化 {pc7d:+.1f}%，趋势明显")

    # 波动率
    vol = signals.get("volatility")
    if vol is not None:
        if vol > 0.1:
            interp.append(f"⚡ 波动剧烈 (σ={vol:.3f})，市场分歧大")
        elif vol < 0.02:
            interp.append(f"😴 波动很低 (σ={vol:.3f})，市场观点稳定")

    # 资金流向
    net_yes = signals.get("recent_net_yes_flow")
    net_no = signals.get("recent_net_no_flow")
    if net_yes is not None and net_no is not None:
        if abs(net_yes) > abs(net_no) * 2 and net_yes > 100:
            interp.append(f"💰 近期 YES 净买入 {net_yes:.0f}，资金看涨")
        elif abs(net_no) > abs(net_yes) * 2 and net_no > 100:
            interp.append(f"💰 近期 NO 净买入 {net_no:.0f}，资金看跌")

    # 大户集中度
    conc_yes = signals.get("holder_concentration_outcome_0")
    if conc_yes is not None:
        if conc_yes > 70:
            interp.append(f"👤 YES 大户高度集中 (Top5={conc_yes}%)，少数大户主导")
        elif conc_yes < 30:
            interp.append(f"👥 YES 持有分散 (Top5={conc_yes}%)，散户为主")

    # 截止时间
    end_dt = _parse_dt(market.get("endDate"))
    if end_dt:
        days_left = -_delta_days(end_dt)
        if days_left and days_left < 7:
            interp.append(f"⏰ 距结束仅剩 {days_left:.1f} 天，临近结算")

    return interp


def analyze_market_depth(slug: str, history_interval: str = "1m") -> Optional[Dict[str, Any]]:
    """
    单市场深度分析。
    返回 dict 包含: market(元数据), history(价格曲线), holders, trades, signals(数值信号), interp(人话解读)
    """
    market = fetch_market_by_slug(slug)
    if not market:
        return None

    token_ids = _parse_token_ids(market)
    yes_token = token_ids[0] if token_ids else None

    history = fetch_price_history(yes_token, interval=history_interval) if yes_token else []
    cond_id = market.get("conditionId")
    holders = fetch_holders(cond_id, limit=10) if cond_id else []
    trades = fetch_recent_trades(cond_id, limit=30) if cond_id else []

    signals = _compute_signals(history, trades, holders, market)
    interp = _interpret_signals(signals, market)
    ai = compute_ai_analysis(signals, market, holders, trades)

    return {
        "market": _condense(market),
        "history": history,
        "holders": holders,
        "trades": trades,
        "signals": signals,
        "interp": interp,
        "ai": ai,
    }


# ---------------------------------------------------------------------------
# AI Analysis (四维评分，借鉴 macro_analysis 的方法论)
# ---------------------------------------------------------------------------


def _classify_market(question: str) -> List[str]:
    """从市场标题推断涉及的主题分类（用于宏观维度提示）。"""
    q = (question or "").lower()
    tags = []
    if any(k in q for k in ["bitcoin", "btc", "eth", "ethereum", "crypto", "solana", "xrp", "doge"]):
        tags.append("crypto")
    if any(k in q for k in ["fed", "rate", "inflation", "cpi", "recession", "gdp"]):
        tags.append("macro")
    if any(k in q for k in ["trump", "biden", "election", "president", "senate", "congress"]):
        tags.append("politics")
    if any(k in q for k in ["iran", "russia", "ukraine", "china", "war", "ceasefire", "peace"]):
        tags.append("geopolitics")
    if any(k in q for k in ["nba", "nfl", "fifa", "world cup", "vs.", "vs ", "match"]):
        tags.append("sports")
    if any(k in q for k in ["ai", "openai", "tesla", "nvidia"]):
        tags.append("tech")
    return tags or ["general"]


def _score_to_pill(score: float) -> str:
    """得分 → CSS class hint."""
    if score > 0.2:
        return "pos"
    if score < -0.2:
        return "neg"
    return "neu"


def _dim_market_action(signals: Dict[str, Any], market: Dict[str, Any]) -> Dict[str, Any]:
    """维度1: 市场行情 — 价格变化 + 波动率"""
    pc24 = signals.get("price_change_24h_pct") or 0
    pc7d = signals.get("price_change_7d_pct") or 0
    vol = signals.get("volatility")
    yes_p = _parse_outcomes(market).get("Yes")

    # 评分逻辑：价格趋势 + 波动率，归一到 [-1, 1]
    momentum_score = 0.0
    if pc24 != 0:
        momentum_score += max(-0.4, min(0.4, pc24 / 30))  # 30% 变化映射到 ±0.4
    if pc7d != 0:
        momentum_score += max(-0.4, min(0.4, pc7d / 50))  # 50% 变化映射到 ±0.4

    # 极端价格（接近 0 或 1）说明已经定价完毕，行情阶段尾声
    edge_penalty = 0.0
    if yes_p is not None:
        if yes_p > 0.95 or yes_p < 0.05:
            edge_penalty = -0.2

    score = round(max(-1, min(1, momentum_score + edge_penalty)), 2)

    facts = []
    if pc24:
        facts.append(f"24h 价格变化 {pc24:+.1f}%")
    if pc7d:
        facts.append(f"7d 累计变化 {pc7d:+.1f}%")
    if vol is not None:
        facts.append(f"波动率 σ={vol:.3f}")
    if yes_p is not None:
        facts.append(f"YES 当前 {yes_p:.1%}")

    if pc7d > 10 and pc24 > 0:
        mech = "近期价格持续走强，多头动能延续，反映市场对 YES 信心增强"
    elif pc7d < -10 and pc24 < 0:
        mech = "价格连续下挫，市场对 YES 的预期持续降温"
    elif vol is not None and vol > 0.1:
        mech = "波动剧烈，多空分歧大，价格未达共识"
    elif yes_p is not None and (yes_p > 0.95 or yes_p < 0.05):
        mech = "市场已基本定价完毕，剩余博弈空间小"
    else:
        mech = "价格相对平稳，市场观点分歧不大"

    if score > 0.3:
        conclusion = "动量偏多，趋势延续"
    elif score < -0.3:
        conclusion = "动量偏空，趋势承压"
    else:
        conclusion = "动量中性，缺乏方向"

    return {
        "name": "市场行情",
        "score": score,
        "facts": facts,
        "mechanism": mech,
        "conclusion": conclusion,
        "pill": _score_to_pill(score),
    }


def _dim_capital_flow(signals: Dict[str, Any]) -> Dict[str, Any]:
    """维度2: 资金流向 — 大单成交方向 + 大户集中度"""
    net_yes = signals.get("recent_net_yes_flow") or 0
    net_no = signals.get("recent_net_no_flow") or 0
    conc_yes = signals.get("holder_concentration_outcome_0")
    conc_no = signals.get("holder_concentration_outcome_1")
    trades_count = signals.get("trades_count", 0)

    # 资金净流向得分：YES 净流入大于 NO 加分
    flow_score = 0.0
    flow_diff = net_yes - net_no
    if abs(flow_diff) > 100:
        flow_score = max(-0.6, min(0.6, flow_diff / 10000))

    # 大户集中度：高度集中 → 风险加分（操纵嫌疑），分散 → 减分（共识）
    risk_score = 0.0
    if conc_yes is not None and conc_yes > 70:
        risk_score -= 0.2
    if conc_no is not None and conc_no > 70:
        risk_score -= 0.2

    score = round(max(-1, min(1, flow_score + risk_score)), 2)

    facts = []
    if net_yes:
        facts.append(f"YES 近期净买入 {net_yes:+,.0f}")
    if net_no:
        facts.append(f"NO 近期净买入 {net_no:+,.0f}")
    if conc_yes is not None:
        facts.append(f"YES Top5 占 {conc_yes}%")
    if conc_no is not None:
        facts.append(f"NO Top5 占 {conc_no}%")
    facts.append(f"近 {trades_count} 笔成交")

    if flow_diff > 1000:
        mech = "资金明显偏向 YES，多头主动建仓"
    elif flow_diff < -1000:
        mech = "资金明显偏向 NO，空头主动建仓"
    elif conc_yes and conc_yes > 70:
        mech = "YES 大户高度集中，少数账户主导，需警惕筹码分歧"
    else:
        mech = "买卖力量相对均衡，无明显倾斜"

    if score > 0.3:
        conclusion = "资金看多 YES"
    elif score < -0.3:
        conclusion = "资金看空 YES / 偏好 NO"
    else:
        conclusion = "资金面中性"

    return {
        "name": "资金流向",
        "score": score,
        "facts": facts,
        "mechanism": mech,
        "conclusion": conclusion,
        "pill": _score_to_pill(score),
    }


def _dim_time_window(market: Dict[str, Any]) -> Dict[str, Any]:
    """维度3: 时间窗口 — 距结束天数 vs 当前定价的合理性"""
    end_dt = _parse_dt(market.get("endDate"))
    days_left = (-_delta_days(end_dt)) if end_dt else None

    yes_p = _parse_outcomes(market).get("Yes")

    score = 0.0
    facts = []
    mech = ""

    if days_left is not None:
        facts.append(f"距结算 {days_left:.1f} 天")
        if days_left < 3:
            facts.append("即将结算")
            # 临近结算，价格应趋向 0 或 1
            if yes_p is not None and 0.2 < yes_p < 0.8:
                score -= 0.4
                mech = "即将结算但价格仍在中间区域，结果不确定性高，价格可能剧烈波动"
            else:
                score += 0.2
                mech = "即将结算且价格已偏向一端，市场基本定型"
        elif days_left < 14:
            facts.append("短期市场")
            mech = "结算窗口较短，事件确定性正在提高"
            score += 0.1
        elif days_left > 180:
            facts.append("长期市场")
            mech = "距结算较久，期间事件变量多，价格易反复波动"
            score -= 0.1
        else:
            mech = "结算窗口适中，市场处于价格发现阶段"
    else:
        mech = "无结算时间数据"

    score = round(max(-1, min(1, score)), 2)

    if score > 0.1:
        conclusion = "时间窗口对当前定价有利"
    elif score < -0.1:
        conclusion = "时间窗口存在不确定性风险"
    else:
        conclusion = "时间窗口中性"

    return {
        "name": "时间窗口",
        "score": score,
        "facts": facts,
        "mechanism": mech,
        "conclusion": conclusion,
        "pill": _score_to_pill(score),
    }


def _dim_macro_context(market: Dict[str, Any], holders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """维度4: 宏观/主题关联 — 推断市场所属类别并给出宏观提示"""
    question = market.get("question", "")
    tags = _classify_market(question)

    score = 0.0
    facts = [f"市场分类: {', '.join(tags)}"]
    holder_count = sum(len(t.get("holders", [])) for t in holders)
    if holder_count > 0:
        facts.append(f"参与持仓地址 {holder_count} 个")

    mech_parts = []
    if "crypto" in tags:
        mech_parts.append("加密类预测受 BTC 主趋势、链上情绪、监管动态影响")
    if "geopolitics" in tags:
        mech_parts.append("地缘类预测对突发事件极敏感（停火、谈判、军事行动）")
    if "politics" in tags:
        mech_parts.append("政治类预测受民调、官方表态、关键日期影响")
    if "macro" in tags:
        mech_parts.append("宏观类预测看 Fed 路径、CPI/PCE、就业数据、市场情绪")
    if "sports" in tags:
        mech_parts.append("体育类预测主要看赔率、伤病、近期表现，结果较快出炉")
        score += 0.1  # 体育类预测的不确定性相对可量化
    if "tech" in tags:
        mech_parts.append("科技类预测看公司业绩、产品发布、行业趋势")

    mech = "；".join(mech_parts) if mech_parts else "通用类预测，建议关注事件进展"

    # 流动性高 → 群体信心 → 加分
    liquidity = _safe_float(market.get("liquidity"))
    if liquidity > 500_000:
        score += 0.1
        facts.append("流动性充足，价格发现充分")
    elif liquidity < 5_000:
        score -= 0.2
        facts.append("流动性偏低，单笔大单可能造成滑点")

    score = round(max(-1, min(1, score)), 2)

    if score > 0.1:
        conclusion = "外部环境支撑当前定价"
    elif score < -0.1:
        conclusion = "外部环境/流动性存在隐患"
    else:
        conclusion = "外部环境中性，关注主题催化"

    return {
        "name": "宏观/主题",
        "score": score,
        "facts": facts,
        "mechanism": mech,
        "conclusion": conclusion,
        "pill": _score_to_pill(score),
    }


def compute_ai_analysis(signals: Dict[str, Any],
                        market: Dict[str, Any],
                        holders: List[Dict[str, Any]],
                        trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    四维 AI 分析（启发式，本地计算）。
    返回:
    {
        verdict: "..." (一句话总结),
        composite_score: float,
        dimensions: [{name, score, facts, mechanism, conclusion, pill}, ...],
        action: "..." (操作建议),
    }
    """
    dims = [
        _dim_market_action(signals, market),
        _dim_capital_flow(signals),
        _dim_time_window(market),
        _dim_macro_context(market, holders),
    ]

    composite = round(sum(d["score"] for d in dims) / len(dims), 2)
    yes_p = _parse_outcomes(market).get("Yes")

    # 综合判断
    if composite > 0.3:
        verdict = "综合评估：YES 方占优，多头动能与资金面同时支撑"
    elif composite < -0.3:
        verdict = "综合评估：NO 方占优，价格承压且资金面偏空"
    elif abs(composite) <= 0.1:
        verdict = "综合评估：多空相对均衡，市场缺乏方向性"
    else:
        verdict = "综合评估：方向偏弱，未形成明确共识"

    # 操作建议（基于 composite + 当前价格）
    action = _build_action_recommendation(composite, yes_p, market, signals)

    return {
        "verdict": verdict,
        "composite_score": composite,
        "dimensions": dims,
        "action": action,
        "tags": _classify_market(market.get("question", "")),
    }


def _build_action_recommendation(composite: float, yes_p: Optional[float],
                                  market: Dict[str, Any],
                                  signals: Dict[str, Any]) -> str:
    """根据综合评分给出操作建议。"""
    if yes_p is None:
        return "数据不足，无法给出建议"

    days_left = market.get("days_until_end")
    liquidity = _safe_float(market.get("liquidity"))

    cautions = []
    if liquidity < 5_000:
        cautions.append("流动性偏低，注意滑点")
    if days_left is not None and days_left < 3:
        cautions.append("临近结算，价格随时可能跳变")
    if yes_p > 0.95 or yes_p < 0.05:
        cautions.append("已极端定价，剩余空间有限")

    # 主建议
    if composite > 0.3 and yes_p < 0.7:
        main = f"信号偏多，YES 当前 {yes_p:.1%}，仍有上行空间"
    elif composite > 0.3 and yes_p >= 0.7:
        main = f"信号偏多但 YES 已达 {yes_p:.1%}，安全边际收窄"
    elif composite < -0.3 and yes_p > 0.3:
        main = f"信号偏空，可考虑做空 YES（即买 NO 当前 {1-yes_p:.1%}）"
    elif composite < -0.3 and yes_p <= 0.3:
        main = f"信号偏空但 YES 已低至 {yes_p:.1%}，下行空间有限"
    else:
        main = "信号中性，建议观望或等待催化事件"

    if cautions:
        return f"{main}。注意：{' / '.join(cautions)}"
    return main


# ---------------------------------------------------------------------------
# Pretty printers (text only)
# ---------------------------------------------------------------------------


def _fmt_money(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"


def _fmt_market_line(m: Dict[str, Any], idx: Optional[int] = None) -> str:
    prefix = f"{idx}. " if idx is not None else ""
    outcomes = m["outcomes"]
    if "Yes" in outcomes and "No" in outcomes:
        prob = f"YES {outcomes['Yes']:.1%} / NO {outcomes['No']:.1%}"
    else:
        prob = " / ".join(f"{k} {v:.1%}" for k, v in list(outcomes.items())[:3])
    return (
        f"{prefix}{m['question']}\n"
        f"   {prob}  |  24h {_fmt_money(m['volume_24h'])}  |  "
        f"流动性 {_fmt_money(m['liquidity'])}\n"
        f"   {m['url']}"
    )


def format_trending(markets: List[Dict[str, Any]]) -> str:
    if not markets:
        return "暂无热门市场（API 可能不可用）"
    lines = ["📈 Polymarket 热门市场（按 24h 成交量）", ""]
    for i, m in enumerate(markets, 1):
        lines.append(_fmt_market_line(m, i))
        lines.append("")
    return "\n".join(lines)


def format_new(markets: List[Dict[str, Any]], days: int) -> str:
    if not markets:
        return f"过去 {days} 天没有符合条件的新市场"
    lines = [f"🆕 Polymarket 最近 {days} 天新上线市场", ""]
    for i, m in enumerate(markets, 1):
        age = m.get("days_since_created")
        age_str = f"{age:.1f}天前" if age is not None else "—"
        lines.append(_fmt_market_line(m, i))
        lines.append(f"   创建于 {age_str}")
        lines.append("")
    return "\n".join(lines)


def format_search(markets: List[Dict[str, Any]], keyword: str) -> str:
    if not markets:
        return f"没有找到包含 “{keyword}” 的市场"
    lines = [f"🔍 搜索 “{keyword}” → {len(markets)} 个结果", ""]
    for i, m in enumerate(markets, 1):
        lines.append(_fmt_market_line(m, i))
        lines.append("")
    return "\n".join(lines)


def format_category(markets: List[Dict[str, Any]], category: str) -> str:
    if not markets:
        return f"分类 “{category}” 暂无活跃市场"
    lines = [f"🏷️ Polymarket 分类「{category}」热门市场", ""]
    for i, m in enumerate(markets, 1):
        lines.append(_fmt_market_line(m, i))
        if m.get("event_title") and m["event_title"] != m["question"]:
            lines.append(f"   📁 事件: {m['event_title']}")
        lines.append("")
    return "\n".join(lines)


def format_depth(analysis: Dict[str, Any]) -> str:
    """格式化单市场深度分析结果。"""
    if not analysis:
        return "未找到该市场"
    m = analysis["market"]
    interp = analysis.get("interp", [])
    signals = analysis.get("signals", {})
    holders = analysis.get("holders", [])

    lines = [
        f"🔍 深度分析: {m['question']}",
        "",
        f"💲 当前: " + " / ".join(f"{k} {v:.1%}" for k, v in m["outcomes"].items()),
        f"📊 24h成交 {_fmt_money(m['volume_24h'])}  |  流动性 {_fmt_money(m['liquidity'])}",
    ]
    if m.get("days_until_end"):
        lines.append(f"⏰ 距结束还有 {m['days_until_end']:.1f} 天")
    lines.append("")

    if interp:
        lines.append("【信号解读】")
        for s in interp:
            lines.append(f"  {s}")
        lines.append("")

    if signals:
        lines.append("【数值信号】")
        for k, v in signals.items():
            lines.append(f"  {k} = {v}")
        lines.append("")

    # Top 大户
    if holders:
        lines.append("【YES Top 5 大户】")
        yes_holders = []
        for token_data in holders:
            holders_list = token_data.get("holders", [])
            if holders_list and holders_list[0].get("outcomeIndex") == 0:
                yes_holders = holders_list[:5]
                break
        for h in yes_holders:
            name = h.get("name") or h.get("pseudonym") or h.get("proxyWallet", "")[:10]
            amount = _safe_float(h.get("amount"))
            lines.append(f"  {name}: {amount:,.0f} 股")
        lines.append("")

    lines.append(f"🔗 {m['url']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "trending"

    if cmd == "trending":
        print(format_trending(list_trending_markets(limit=15)))
    elif cmd == "new":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        print(format_new(list_new_markets(days=days, limit=15), days=days))
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("用法: python3 polymarket_analyzer.py search <keyword>")
            sys.exit(1)
        kw = sys.argv[2]
        print(format_search(search_markets(kw), kw))
    elif cmd == "category":
        if len(sys.argv) < 3:
            print("可选分类:", ", ".join(list_categories()))
            sys.exit(0)
        cat = sys.argv[2]
        print(format_category(list_by_category(cat, limit=15), cat))
    elif cmd == "depth":
        if len(sys.argv) < 3:
            print("用法: python3 polymarket_analyzer.py depth <slug>")
            sys.exit(1)
        slug = sys.argv[2]
        result = analyze_market_depth(slug)
        print(format_depth(result))
    else:
        print("用法: python3 polymarket_analyzer.py [trending|new|search|category|depth] [args]")
