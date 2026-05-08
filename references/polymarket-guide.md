# Polymarket 预测市场分析指南

> Polymarket 是基于 Polygon 区块链的预测市场平台，本工具提供：看盘 / 标的发现 / 单市场深度解读 / 飞书关注列表。

## 一、设计目标

- **不做套利扫描**（v0.1 验证：API 返回 YES+NO 总和恒为 1，"价差套利"在 Gamma API 层面不可见，需要 CLOB 订单簿 + 跨市场组合，超出本工具范围）
- **专注三件事**：
  1. 看盘：热门 / 新上线 / 分类 / 关键词搜索
  2. 单市场深度解读：价格历史 + 大户持仓 + 资金流向 + 多维评分
  3. 飞书关注列表：跟踪感兴趣的市场，定时刷新

## 二、模块结构

| 模块 | 职责 |
|------|------|
| `polymarket_analyzer.py` | 核心分析（数据拉取 + 指标计算 + 文本输出） |
| `polymarket_dashboard.py` | 主看板 HTML（分类 Tabs + 热门 + 新上线 + 深度解读按钮） |
| `polymarket_market_report.py` | 单市场深度报告 HTML（价格曲线 + 多维评分 + 大户榜单 + Markdown 解读注入） |
| `polymarket_watchlist.py` | 飞书多维表格收藏关注列表（首次调用自动建表） |

## 三、数据源

全部使用 Polymarket 公开 API，**无需 auth key**：

| API | URL | 用途 |
|-----|-----|------|
| Gamma | `gamma-api.polymarket.com/markets` `gamma-api.polymarket.com/events` | 市场元数据、分类、列表 |
| CLOB | `clob.polymarket.com/prices-history` | 价格历史曲线 |
| Data | `data-api.polymarket.com/holders` `data-api.polymarket.com/trades` | 大户持仓、最近成交 |

仅依赖 Python 标准库（`urllib`、`json`），无外部包依赖。

## 四、四维评分模型

参考宏观策略框架（多维度评分 + 综合判断 + 操作建议），单市场深度解读包含 4 个维度：

| 维度 | 输入证据 | 信号产物 |
|------|---------|---------|
| **市场行情** | 24h/7d 价格变化、波动率、当前 YES 概率、极端定价惩罚 | 动量 +/中/- |
| **资金流向** | YES/NO 净买入、大户 Top5 集中度、成交笔数 | 多空 +/中/- |
| **时间窗口** | 距 trading 截止天数、结算区间 vs 中间区域定价匹配度 | 时间 +/中/- |
| **宏观/主题** | 标题关键词推断分类(crypto/政治/地缘/体育)、流动性分级 | 环境 +/中/- |

每个维度输出：得分 (-1 ~ +1) + 事实清单 + 机制解释 + 一句话结论。
综合得分 = 4 维平均，加上**自动化操作建议**（识别"已极端定价"/"流动性低"/"临近结算"等警示）。

## 五、Claude 深度解读流程

主看板每个市场卡片有 **🔍 深度解读** 按钮，点击 → 复制 prompt 到剪贴板 → 回到对话粘贴并发送 → Claude 接收后：

1. 调用 `analyze_market_depth(slug)` 拉真实数据（530+ 价格点 + 大户 + 成交 + 多维评分）
2. 基于真实数据**亲自撰写一份 markdown 深度解读**，结构为：市场概况 / 当前定价是否合理 / 关键变量 / 反转剧本 / 执行建议
3. 调用 `generate_market_report(slug, claude_analysis=md)` 注入 markdown 到 HTML 报告
4. 在对话中返回 2-3 句简短摘要

## 六、HTML 报告输出路径

```
~/Desktop/stock-master/reports/
├── polymarket_dashboard_YYYYMMDD_HHMM.html         # 主看板
└── polymarket_<slug>_YYYYMMDD_HHMM.html            # 单市场深度报告
```

## 七、命令行用法

```bash
cd scripts/

# 看热门
python3 polymarket_analyzer.py trending

# 最近新上线
python3 polymarket_analyzer.py new 7

# 分类浏览（政治/加密/体育/地缘/科技/经济/娱乐）
python3 polymarket_analyzer.py category 政治

# 关键词搜索
python3 polymarket_analyzer.py search bitcoin

# 单市场深度文本输出
python3 polymarket_analyzer.py depth <slug>

# 主看板 HTML
python3 polymarket_dashboard.py

# 单市场深度报告 HTML
python3 polymarket_market_report.py <slug>

# 飞书关注列表
python3 polymarket_watchlist.py add <slug> [category] [note]
python3 polymarket_watchlist.py list
python3 polymarket_watchlist.py refresh
python3 polymarket_watchlist.py remove <slug>
```

## 八、关键数据陷阱

⚠️ **`endDate` 字段 ≠ question 里赌的日期**

Polymarket 很多市场是"提前 resolve 型"——条件触发就立刻结算，否则继续挂着等问题里的截止日期。`endDate` / `trading_end_date` 实际是 **market 停止接受订单的时间**。

例：market `microstrategy-sells-any-bitcoin-by-december-31-2026`，question 写 12/31/2026，但 `endDate=2026-07-01` —— 这是 trading 阶段截止 / 审查窗口，不是结算日。

**判断真实结算日期**：看 `groupItemTitle` 字段（如 "December 31, 2026"）或 question 文本。永远不要用 `endDate` 去说"距结算还有 N 天"。

## 九、已知限制

- **不做套利扫描**：v0.1 已验证 Gamma API 给出的 outcomePrices 是归一化中间价，YES+NO 永远 = 1
- **多选市场（3+ outcomes）的多维评分不准**：现在主要按 YES/NO 二元假设设计
- **错误降级简单**：API 任一挂了只是返回空数据，没有重试机制（后续版本计划增加）
