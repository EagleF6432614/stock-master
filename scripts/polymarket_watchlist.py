"""
Polymarket 飞书收藏关注列表 v0.2

功能：
- 在飞书多维表格创建一张 "polymarket_watchlist" 表
- 添加/更新/删除关注的市场
- 支持按 slug 主键去重，自动刷新最新价格

表结构：
- 市场标题 (文本)
- slug (文本，主键)
- YES概率 (数字)
- NO概率 (数字)
- 24h成交 (数字)
- 流动性 (数字)
- 截止日期 (日期)
- 分类 (多选)
- 添加时间 (日期)
- 备注 (文本)
- 链接 (URL)
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from feishu_sync import FeishuBitable, to_feishu_timestamp
from polymarket_analyzer import fetch_market_by_slug, _condense, _safe_float


WATCHLIST_TABLE_NAME = "polymarket_watchlist"
CONFIG_KEY = "polymarket_watchlist"

DEFAULT_CONFIG_PATH = str(Path.home() / "Desktop" / "stock-master" / "feishu_config.json")


# 多维表格字段类型常量
FIELD_TEXT = 1
FIELD_NUMBER = 2
FIELD_SINGLE_SELECT = 3
FIELD_MULTI_SELECT = 4
FIELD_DATE = 5
FIELD_URL = 15


WATCHLIST_FIELDS = [
    {"field_name": "市场标题", "type": FIELD_TEXT},
    {"field_name": "slug", "type": FIELD_TEXT},
    {"field_name": "YES概率", "type": FIELD_NUMBER, "property": {"formatter": "0.0%"}},
    {"field_name": "NO概率", "type": FIELD_NUMBER, "property": {"formatter": "0.0%"}},
    {"field_name": "24h成交", "type": FIELD_NUMBER, "property": {"formatter": "0"}},
    {"field_name": "流动性", "type": FIELD_NUMBER, "property": {"formatter": "0"}},
    {"field_name": "截止日期", "type": FIELD_DATE, "property": {"date_formatter": "yyyy-MM-dd"}},
    {"field_name": "分类", "type": FIELD_MULTI_SELECT, "property": {
        "options": [
            {"name": "政治"}, {"name": "加密"}, {"name": "体育"},
            {"name": "地缘"}, {"name": "科技"}, {"name": "经济"}, {"name": "娱乐"}
        ]
    }},
    {"field_name": "添加时间", "type": FIELD_DATE, "property": {"date_formatter": "yyyy-MM-dd HH:mm"}},
    {"field_name": "备注", "type": FIELD_TEXT},
    {"field_name": "链接", "type": FIELD_URL},
]


def _ensure_watchlist_table(bitable: FeishuBitable, config_path: str) -> str:
    """
    确保 polymarket_watchlist 表存在，返回 table_id。
    如果配置文件中已记录则直接用，否则创建新表并把 id 写回配置。
    """
    # 重新加载配置看有没有缓存的 table_id
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    cached_id = config.get("TABLES", {}).get(CONFIG_KEY)
    if cached_id:
        return cached_id

    # 创建新表
    print(f"[polymarket watchlist] 创建新表 {WATCHLIST_TABLE_NAME}...")
    result = bitable.create_table(WATCHLIST_TABLE_NAME, WATCHLIST_FIELDS)
    table_id = result.get("data", {}).get("table_id")
    if not table_id:
        raise RuntimeError(f"创建表失败: {result}")

    # 回写配置
    config.setdefault("TABLES", {})[CONFIG_KEY] = table_id
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"[polymarket watchlist] 表创建成功 table_id={table_id}")
    return table_id


def _market_to_record(market: Dict[str, Any], category: Optional[str] = None,
                      note: str = "") -> Dict[str, Any]:
    """把 _condense 后的市场数据转换为飞书记录字段。"""
    outcomes = market.get("outcomes", {})
    end_iso = market.get("end_date")
    end_ts = None
    if end_iso:
        try:
            end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
            end_ts = int(end_dt.timestamp() * 1000)
        except (ValueError, TypeError):
            end_ts = None

    fields = {
        "市场标题": market.get("question", ""),
        "slug": market.get("slug", ""),
        "YES概率": outcomes.get("Yes", 0),
        "NO概率": outcomes.get("No", 0),
        "24h成交": _safe_float(market.get("volume_24h")),
        "流动性": _safe_float(market.get("liquidity")),
        "添加时间": int(time.time() * 1000),
        "链接": {"link": market.get("url", ""), "text": "Polymarket"},
    }
    if end_ts:
        fields["截止日期"] = end_ts
    if category:
        fields["分类"] = [category]
    if note:
        fields["备注"] = note
    return fields


def add_to_watchlist(slug: str, category: Optional[str] = None,
                     note: str = "", config_path: Optional[str] = None) -> Dict[str, Any]:
    """添加市场到飞书关注列表。如果已存在则更新最新价格。"""
    bitable = FeishuBitable(config_path)
    cfg_path = config_path or str(bitable.config_path) if hasattr(bitable, "config_path") else DEFAULT_CONFIG_PATH
    table_id = _ensure_watchlist_table(bitable, cfg_path)

    # 拉市场数据
    raw = fetch_market_by_slug(slug)
    if not raw:
        return {"ok": False, "error": f"slug 未找到: {slug}"}
    market = _condense(raw)
    fields = _market_to_record(market, category, note)

    # 看是否已存在
    existing = bitable.find_record_by_field("slug", slug, table_id=table_id)
    if existing:
        record_id = existing.get("record_id")
        result = bitable.update_record(record_id, fields, table_id=table_id)
        return {"ok": True, "action": "updated", "slug": slug, "record_id": record_id}
    else:
        result = bitable.create_record(fields, table_id=table_id)
        record_id = result.get("data", {}).get("record", {}).get("record_id")
        return {"ok": True, "action": "created", "slug": slug, "record_id": record_id}


def remove_from_watchlist(slug: str,
                          config_path: Optional[str] = None) -> Dict[str, Any]:
    """从关注列表移除某市场。"""
    bitable = FeishuBitable(config_path)
    cfg_path = config_path or DEFAULT_CONFIG_PATH
    table_id = _ensure_watchlist_table(bitable, cfg_path)

    existing = bitable.find_record_by_field("slug", slug, table_id=table_id)
    if not existing:
        return {"ok": False, "error": f"未在关注列表: {slug}"}
    record_id = existing.get("record_id")
    bitable.delete_record(record_id, table_id=table_id)
    return {"ok": True, "action": "removed", "slug": slug}


def list_watchlist(config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出所有关注的市场。"""
    bitable = FeishuBitable(config_path)
    cfg_path = config_path or DEFAULT_CONFIG_PATH
    table_id = _ensure_watchlist_table(bitable, cfg_path)
    records = bitable.list_records(table_id=table_id, page_size=100)
    return [r.get("fields", {}) for r in records]


def refresh_watchlist(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    刷新所有关注市场的最新价格/成交/流动性。
    用于定期同步。
    """
    items = list_watchlist(config_path)
    updated, failed = 0, 0
    errors = []
    for item in items:
        slug = item.get("slug")
        if not slug:
            continue
        try:
            r = add_to_watchlist(slug, config_path=config_path)
            if r.get("ok"):
                updated += 1
            else:
                failed += 1
                errors.append(r.get("error"))
        except Exception as e:
            failed += 1
            errors.append(str(e))
    return {"ok": failed == 0, "updated": updated, "failed": failed, "errors": errors}


def format_watchlist(items: List[Dict[str, Any]]) -> str:
    """文本格式化输出 watchlist。"""
    if not items:
        return "📭 关注列表为空。可用 `add_to_watchlist(slug)` 添加。"
    lines = [f"⭐ Polymarket 关注列表 ({len(items)} 个)", ""]
    for i, item in enumerate(items, 1):
        title = item.get("市场标题", "—")
        yes = _safe_float(item.get("YES概率"))
        no = _safe_float(item.get("NO概率"))
        vol = _safe_float(item.get("24h成交"))
        slug = item.get("slug", "")
        lines.append(f"{i}. {title}")
        lines.append(f"   YES {yes:.1%} / NO {no:.1%}  |  24h ${vol:,.0f}")
        lines.append(f"   slug: {slug}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 polymarket_watchlist.py add <slug> [category] [note]")
        print("  python3 polymarket_watchlist.py remove <slug>")
        print("  python3 polymarket_watchlist.py list")
        print("  python3 polymarket_watchlist.py refresh")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "add":
        if len(sys.argv) < 3:
            print("缺少 slug 参数")
            sys.exit(1)
        slug = sys.argv[2]
        cat = sys.argv[3] if len(sys.argv) > 3 else None
        note = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(add_to_watchlist(slug, cat, note), ensure_ascii=False, indent=2))
    elif cmd == "remove":
        slug = sys.argv[2]
        print(json.dumps(remove_from_watchlist(slug), ensure_ascii=False, indent=2))
    elif cmd == "list":
        print(format_watchlist(list_watchlist()))
    elif cmd == "refresh":
        print(json.dumps(refresh_watchlist(), ensure_ascii=False, indent=2))
    else:
        print(f"未知命令: {cmd}")
