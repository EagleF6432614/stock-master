---
name: stock-master
description: 综合性股票技术分析工具，小白友好。混合数据源（Yahoo Finance + Alpha Vantage MCP），输出通俗易懂的技术分析、买卖建议和交互式可视化报告。支持美股/港股/A股、持仓盈亏分析、PDF导出、大盘看板。当用户提到任何股票代码（TSLA、0700.HK、688028）、公司名（苹果、茅台、沃尔德）、或请求股票分析、技术指标、交易建议、持仓分析、大盘数据、小白建议、导出报告时激活。即使用户只说"分析一下"或"能买吗"，只要上下文涉及股票，都应激活此 skill。
---
# Stock Master v4.6

面向普通投资者的技术分析工具。核心原则：**用日常语言解释技术指标，给出明确可执行的买卖建议。**

## 目标与约束

### 用户画像
普通散户投资者，可能不懂技术术语。所有输出必须让完全没有股票知识的人也能理解并据此行动。

### 输出质量约束
1. **结论先行** — 先给结论（买/卖/观望），再给理由和数据支撑
2. **可执行** — 每个建议必须带具体价格和数量，不说"可以考虑"这种模糊话
3. **风险对称** — 有买入建议就必须同时给止损价，有止盈就必须说清触发条件
4. **小白友好** — 每个技术指标必须用生活化比喻解释（汽车油门/橡皮筋/红绿灯等），参考 `scripts/beginner_analyzer.py` 中 `explain_*_simple()` 系列函数的风格
5. **数据透明** — 展示评分明细，让用户知道每个指标对最终评分的贡献
6. **风险提示** — 每份分析必须包含：仅供参考不构成投资建议、股市有风险投资需谨慎、建议分批建仓设置止损

### 禁止行为
- 不输出没有数据支撑的判断
- 不在报告中使用"可能""也许""或者"等模糊词作为操作建议（分析解释中可用）
- 评分超出 [-10, +10] 范围时必须截断
- 不在分析中混入个人观点，所有判断基于指标数据

### 错误处理
- ticker 无效或 `analyze_stock_local()` 返回 `{'error': ...}` → 告知用户并建议检查代码（A股需 `.SS`/`.SZ` 后缀，港股需 `.HK`）
- 数据不足（< 20 个交易日）→ 部分指标可能返回默认值（RSI=50, KDJ 返回 `{'error': '数据不足'}`），分析中注明"数据周期较短，结论仅供参考"
- 某个指标返回 `{'error': ...}` → 跳过该指标，评分中标注"XX指标因数据不足未参与评分"

## 数据获取

### 数据源优先级
| 数据 | 美股 | 港股/A股 |
|------|------|----------|
| 价格+OHLCV | Yahoo Finance | Yahoo Finance |
| RSI/布林带 | Alpha Vantage MCP → 失败降级本地 | 本地计算 |
| MACD/KDJ/ATR/均线/OBV/形态 | 本地计算 | 本地计算 |

### 代码识别
- 中文股票名 → 搜索对应代码
- A股：加 `.SS`（上交所）或 `.SZ`（深交所）后缀
- 港股：加 `.HK` 后缀
- 美股：直接使用 ticker

### 容错策略
- Alpha Vantage MCP：失败 → 等 2s 重试 1 次 → 仍失败 → 降级到本地计算，报告中注明数据来源
- Yahoo Finance：超时重试 2 次（2s → 4s 指数退避）
- 429/限流：标记当天已限流，后续直接本地计算

## 核心脚本与数据结构

### 一键分析

`scripts/indicators.py` → `analyze_stock_local(ticker, period='3mo')`

返回值结构（所有分析的数据基础）：
```python
{
    'ticker': str,              # 'TSLA', '688028.SS'
    'current_price': float,
    'timestamp': str,           # ISO format
    'source': str,
    'indicators': {
        'rsi': float,           # 0-100，数据不足时返回 50.0
        'bbands': {'upper': float, 'middle': float, 'lower': float, 'bandwidth': float},
        'macd': {
            'macd_line': float, 'signal_line': float,
            'histogram': float, 'prev_histogram': float,
            'signal': str,      # 'golden_cross'|'death_cross'|'bullish'|'bearish'
            'interpretation': str
        },
        'atr': float,           # 绝对值
        'atr_percent': float,   # 百分比
        'ma_system': {
            'ma5': float, 'ma10': float, 'ma20': float,
            'ma60': float|None,  # 数据 < 60天时为 None
            'arrangement': str,  # '多头排列'|'空头排列'|'均线缠绕'
            'trend': str         # 'bullish'|'bearish'|'neutral'
        },
        'volume': {
            'volume_ratio': float, 'pattern': str,
            'signal': str, 'explanation': str
        },
        'kdj': {'k': float, 'd': float, 'j': float, 'signal': str, 'interpretation': str},
        'obv': {'obv': int, 'signal': str, 'interpretation': str},
        'williams_r': {'williams_r': float, 'signal': str, 'interpretation': str},
        'bias': {'bias6': float, 'bias12': float, 'bias24': float, 'signal': str}
    },
    'support_resistance': {
        'supports': [{'price': float, 'type': str, 'strength': str}],   # strength: 'strong'|'medium'|'weak'
        'resistances': [{'price': float, 'type': str, 'strength': str}],
        'nearest_support': {'price': float, ...} | None,
        'nearest_resistance': {'price': float, ...} | None,
        'fibonacci': {'0.0%': float, '23.6%': float, '38.2%': float, '50.0%': float, '61.8%': float, '78.6%': float, '100.0%': float}
    },
    'divergence': {
        'macd': {'divergence': str, 'strength': float, 'interpretation': str},  # 'bullish'|'bearish'|'none'（注意是字符串 'none'，非 Python None）
        'rsi': {'divergence': str, 'strength': float, 'interpretation': str}   # 同上
    },
    'patterns': {
        'all_patterns': [{'name': str, 'signal': str, 'strength': str}],
        'signal': str,          # 'bullish'|'bearish'|'neutral'
        'bullish_count': int, 'bearish_count': int
    },
    'stop_loss': {'stop_loss': float, 'take_profit': float},
    'prices': {'close_1m': list, 'close_3m': list},
    'visualization': { ... }    # swing_points, trend_lines, sr_zones
}
```

### 生成评分

`scripts/beginner_analyzer.py` → `generate_trading_recommendation()`

从 `analyze_stock_local()` 的结果到此函数的参数映射：
```python
result = analyze_stock_local(ticker)
ind = result['indicators']
sr = result['support_resistance']
div = result['divergence']

signal = generate_trading_recommendation(
    ticker=result['ticker'],
    current_price=result['current_price'],
    rsi=ind['rsi'],
    macd_histogram=ind['macd']['histogram'],
    prev_macd_histogram=ind['macd']['prev_histogram'],
    bb_upper=ind['bbands']['upper'],
    bb_middle=ind['bbands']['middle'],
    bb_lower=ind['bbands']['lower'],
    prices_1m=result['prices']['close_1m'],
    prices_3m=result['prices']['close_3m'],
    atr=ind['atr'],
    atr_percent=ind['atr_percent'],
    volume_ratio=ind['volume']['volume_ratio'],
    volume_signal=ind['volume']['signal'],
    ma_trend=ind['ma_system']['trend'],
    ma_arrangement=ind['ma_system']['arrangement'],
    kdj_k=ind['kdj']['k'],
    kdj_d=ind['kdj']['d'],
    kdj_j=ind['kdj']['j'],
    kdj_signal=ind['kdj']['signal'],
    macd_divergence=div['macd']['divergence'],
    rsi_divergence=div['rsi']['divergence'],
    obv_signal=ind['obv']['signal'],
    williams_signal=ind['williams_r']['signal'],
    bias_signal=ind['bias']['signal'],
    nearest_support=sr['nearest_support']['price'] if sr['nearest_support'] else None,
    nearest_resistance=sr['nearest_resistance']['price'] if sr['nearest_resistance'] else None,
    patterns_signal=result['patterns']['signal'],
    patterns_data=result['patterns']
)
```

返回 `TradingSignal` 对象，关键属性：
- `action`: str — `'BUY'`|`'SELL'`|`'HOLD'`
- `score`: int — 综合评分
- `score_breakdown`: list[dict] — 每项为 `{'indicator': str, 'value': str, 'signal': str, 'score': int}`
- `stop_loss`, `take_profit`: float
- `buy_price`, `sell_price`: float|None — 建议买入/卖出价
- `confidence`: str — `'高'`|`'中'`|`'低'`
- `reasons`: list[str] — 理由列表
- `suggested_position`: float — 建议仓位百分比
- `risk_reward_ratio`: float|None — 风险收益比
- `atr`, `atr_percent`: float|None

### HTML 报告

`scripts/beginner_analyzer.py` → `generate_html_report(ticker, name, analysis_result, signal, stock_data)`

- `analysis_result`: `analyze_stock_local()` 的返回值
- `signal`: `generate_trading_recommendation()` 的返回值
- `stock_data`: 原始 OHLCV 数据字典（从 `get_stock_data()` 获取）
- 返回：HTML 文件路径（成功）或 Markdown 字符串（失败时回退）

### 大盘看板

`scripts/market_dashboard.py` → `generate_market_dashboard()`

## 评分体系

综合评分 [-10, +10]，基于以下指标加权求和后截断：

| 指标 | 看多信号 | 看空信号 |
|------|---------|---------|
| RSI | <30 超卖 +3 / <40 偏低 +1 | >70 超买 -3 / >60 偏高 -1 |
| MACD | 金叉 +3 / 多头 +1 | 死叉 -3 / 空头 -1 |
| 布林带 | 跌破下轨 +2 / 接近下轨 +1 | 突破上轨 -2 / 接近上轨 -1 |
| KDJ | 金叉 +3 / 超卖 +2 | 死叉 -3 / 超买 -2 |
| MACD背离 | 底背离 +4 | 顶背离 -4 |
| RSI背离 | 底背离 +3 | 顶背离 -3 |
| OBV | 底背离 +2 / 确认上涨 +1 | 顶背离 -2 / 确认下跌 -1 |
| 均线 | 多头排列 +2 | 空头排列 -2 |
| 成交量 | 放量上涨 +2 / 缩量下跌 +1 | 放量下跌 -2 |
| 形态（强） | 三白兵/早晨之星/头肩底/双底 +3 | 三乌鸦/黄昏之星/头肩顶/双顶 -3 |
| 形态（中） | 看涨吞没/上升三角 +2 | 看跌吞没/下降三角 -2 |
| 形态（弱） | 锤子线/倒锤子 +1 | 上吊线/射击之星 -1 |

评分 → 建议映射：≥6 强烈买入(30%) / 3~5 建议买入(20%) / -2~2 观望 / -3~-5 建议卖出 / ≤-6 强烈卖出

指标缺失时：跳过该指标不计分，在评分明细中标注"未参与"。

### 异常量价信号（不参与评分，仅提醒）
- 放量异常：当日成交量 > 20日中位数 × 3
- 缩量异常：当日成交量 < 20日中位数 × 0.3
- 波动异常：当日涨跌幅 > 20日振幅中位数 × 3

## 场景处理

### 场景 A：分析单只股票
触发："分析 TSLA" / "看看苹果" / "0700.HK 能买吗" / "分析沃尔德"

执行：获取数据 → 计算全部指标 → 生成评分 → 输出文字分析 + HTML 报告。AI 自行决定最佳呈现方式，但必须满足上述输出质量约束。

### 场景 B：已持仓分析
触发：用户提供了买入价和持仓量（如 "买入价 78，持有 20000 股"）

场景 B 建立在场景 A 的分析基础上（需先有或同时执行场景 A）。额外要求：
- 计算持仓盈亏（成本/市值/浮盈/收益率），货币单位与股票市场一致（A股=人民币，港股=港元，美股=美元）
- 评估买入位置质量（对比布林带/支撑位/均线）
- 浮盈 > 20% 时，给出分批止盈方案（具体股数 + 目标价 + 每批锁定利润）
- 给出移动止损位（基于最近强支撑位）
- 计算止损后仍可锁定的最低利润

### 场景 C：小白版建议
触发：用户要求"小白版" / "通俗易懂" / "简单说说"

场景 C 是对已有分析（场景 A/B）的二次呈现。如果上下文中没有先行分析，先执行场景 A 再输出小白版。额外要求：
- 用一个核心比喻贯穿全文（钓鱼/开车/打牌等），保持一致性
- 行动步骤用编号列出，每步只说一件事
- 必须回答三个问题：现在该怎么办？什么时候必须跑？现在要不要急着动？
- 最后给出"最重要的三句话"作为总结

### 场景 D：PDF 导出
触发："渲染成 PDF" / "导出 PDF" / "生成报告"

约束：
- 先生成自包含 HTML（内嵌 CSS，无外部依赖，中文字体声明：PingFang SC / Hiragino Sans GB / Microsoft YaHei）
- 使用 Chrome 无头模式转 PDF（`--headless --print-to-pdf --print-to-pdf-no-header`）
- **禁止使用 weasyprint**（中文字体嵌入有 bug 导致乱码）
- 结论在前、图表/详情在后
- 使用 callout 卡片区分信息类型（绿=利好 / 红=风险 / 蓝=解读 / 琥珀=警告 / 紫=小白提示）
- 输出文件复制到桌面并告知路径

### 场景 E：对比多只股票
触发："对比 AAPL 和 GOOGL" / "哪个好"

3 只及以上时用 Task 工具并行分析，最后汇总对比表。

### 场景 F：大盘数据看板
触发："大盘数据" / "看看大盘" / "市场看板" / "今日市场"

调用 `generate_market_dashboard()`，数据来源 Day1 Global API（第三方，不可用时提示错误不影响其他功能）。

### 场景 G：持仓管理
触发："创建持仓表格" / "分析我的持仓"

使用 `scripts/portfolio.py`，Excel 路径默认项目目录下 `my_portfolio.xlsx`。

## HTML 可视化报告

由 `scripts/html_report.py` 的 `HTMLReportGenerator` 生成。

技术栈：TradingView Lightweight Charts v4 (CDN) / 暗色主题 / 自包含 HTML

图表 Toggle 开关（默认只开均线，其余关闭）：均线 / 布林带 / 支撑阻力 / Swing标注 / 趋势线 / 斐波那契

TradingView 跳转映射：`.HK` → `HKEX:` / `.SS` → `SSE:` / `.SZ` → `SZSE:`

报告保存路径：项目目录下 `reports/TICKER_YYYYMMDD_HHMM.html`

失败时自动回退到 Markdown 文字输出。

## 投资智慧模块

[references/investment-wisdom.md](references/investment-wisdom.md) 包含用户个人投资感悟。

使用场景：给出买卖建议时引用相关智慧佐证 / 用户迷茫时引用"十大境界"鼓励 / 风险提示时引用警示内容。

## 参考文档
- [references/investment-wisdom.md](references/investment-wisdom.md) — 投资智慧
- [references/mcp-tools.md](references/mcp-tools.md) — MCP 工具调用
- [references/scripts-guide.md](references/scripts-guide.md) — 脚本说明
- [references/changelog.md](references/changelog.md) — 更新日志
