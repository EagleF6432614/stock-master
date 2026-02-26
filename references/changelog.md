# Stock Master 更新日志

> 每次 Skill 更新后，将迭代内容追加到本文档顶部。

---

## 版本总览

| 版本 | 日期 | 主题 | 一句话概括 |
|------|------|------|-----------|
| v1.0 | 2025-10-23 | 起步 | 基础股票分析，手动查数据 |
| v2.0 | 2026-01-20 | 数据源 | 接入 Alpha Vantage MCP，混合数据源架构 |
| v3.0 | 2026-01-21 | 小白化 | 通俗语言 + 买卖建议 + Excel 持仓管理 |
| v3.1 | 2026-01-21 | 持仓增强 | 交易建议自动写入 Excel |
| v3.2 | 2026-01-21 | 港股+风控 | 港股本地计算、ATR 止损、均线系统 |
| v3.3 | 2026-01-22 | 指标大全 | KDJ、背离检测、OBV、斐波那契、威廉 |
| v3.4 | 2026-01-22 | 形态识别 | K线形态 + 趋势形态 + 评分权重 |
| v3.4.1 | 2026-01-22 | 更名 | stock-analyzer → stock-master |
| v3.5 | 2026-01-22 | 飞书集成 | 分析结果同步到飞书多维表格 |
| v3.6 | 2026-01-25 | 投资智慧 | 融入个人投资感悟，智慧佐证系统 |
| v3.7 | 2026-02-21 | EvoMap 强化 | API 容错、异常检测、飞书降级、并行分析 |
| v4.0 | 2026-02-24 | 可视化报告 | 交互式 HTML 报告、Lightweight Charts K线图、TradingView 跳转 |
| v4.1 | 2026-02-24 | 图表升级 | 图例、Swing标注、趋势线、S/R色带、布林带填充、PriceLine |
| v4.2 | 2026-02-24 | 交互增强 | 指标Toggle开关、评分明细表、小白解读卡片、关键价位表、操作建议 |
| v4.2.1 | 2026-02-24 | 修复+智慧 | SR Toggle修复、投资智慧模块、HTML报告作补充不替代文字输出 |
| v4.2.2 | 2026-02-25 | 智慧精简 | 投资智慧精简为1-2条、真实数据全功能验证通过 |

---

## v4.2.2 (2026-02-25) — 智慧精简 + 全功能验证

### 改进: 投资智慧精简
- 从 3-4 条精简为 **1-2 条**，只展示与当前信号最相关的智慧
- BUY+高分 → 1条牛市智慧 + 1条仓位管理
- SELL → 1条止损 + 1条风险
- HOLD → 1条心态 + 1条风险

### 验证: 真实数据全功能测试 (AAPL)
- K线红绿双色 ✓（真实 OHLC 数据）
- Swing 标注 ✓（8个高低点，toggle 切换正常）
- 趋势线 ✓（上升趋势线，toggle 切换正常）
- 支撑阻力 ✓（S:/R: 标签，toggle 切换正常）
- 布林带/斐波那契 ✓（toggle 切换正常）
- 评分明细表 ✓（10项指标评分）
- 小白解读 ✓（RSI/MACD/KDJ/成交量/均线/布林带 正确数值）
- 投资智慧 ✓（2条精选语录）

### 说明: 前版 Mock 数据问题
- v4.2.1 测试中 Swing/趋势线/K线单色问题均为 mock 数据缺陷（缺少 `visualization` 字段、`open = close - random()` 导致全绿），非代码 bug
- 真实 Yahoo Finance 数据下所有功能正常

### 文件变更
| 文件 | 操作 |
|------|------|
| `scripts/html_report.py` | 投资智慧选取逻辑精简（1-2条） |
| `references/changelog.md` | 更新 |

---

## v4.2.1 (2026-02-24) — 修复 + 投资智慧 + 输出策略

### 修复: 支撑阻力 Toggle 无效果
- **根因**: supports/resistances 的 `type` 字段含 "Fib" 前缀（如 "Fib 38.2%"），导致 JS 中 `label.startsWith('Fib')` 将全部 PriceLine 归入 fib 组，sr 组为空
- **修复**: `_build_sr_js()` 为每条线添加显式 `group` 字段（'fib' 或 'sr'），JS 优先使用 `line.group` 分组
- supports 标签改为 `S: {type}`，resistances 改为 `R: {type}`

### 新增: 投资智慧模块
- `_build_wisdom_section()` — 根据信号类型自动匹配相关智慧语录
- BUY 信号 → 牛熊市智慧 + 仓位管理建议
- SELL 信号 → 止损艺术 + 风险警示
- HOLD 信号 → 核心心法 + 成长智慧
- 始终附带一条风险提醒
- 金色左边框卡片网格布局

### 改进: HTML 报告输出策略
- HTML 报告作为**补充**，不替代 Claude Code 文字输出
- 先输出完整文字分析（`format_detailed_report()`），再在末尾附上 HTML 报告链接
- SKILL.md 执行步骤更新为第 6 步输出文字、第 7 步生成 HTML

### 文件变更
| 文件 | 操作 |
|------|------|
| `scripts/html_report.py` | 修复 SR group 分类 + 新增 `_build_wisdom_section()` + CSS |
| `SKILL.md` | 更新输出策略说明 |
| `references/changelog.md` | 更新 |

---

## v4.2.0 (2026-02-24) — 图表交互 + 文字分析增强

### 新增: 评分明细数据 (`scripts/beginner_analyzer.py`)
- `TradingSignal` 新增 `score_breakdown` 字段 — `List[Dict]`，每项含 indicator/value/signal/score
- `generate_trading_recommendation()` 在所有评分块收集明细（RSI/MACD/布林带/KDJ/背离/OBV/威廉/乖离率/成交量/均线/形态等）

### 新增: 图表指标 Toggle 开关 (`scripts/html_report.py`)
- 药丸形按钮工具栏：均线 | 布林带 | 支撑阻力 | Swing标注 | 趋势线 | 斐波那契
- **默认只开启均线**，其余关闭 — 图表干净，用户按需叠加
- JS 切换逻辑：LineSeries/AreaSeries `visible`、PriceLine `remove/create`、Markers `setMarkers`、Canvas overlay `srZonesVisible`

### 新增: 文字分析增强 (`scripts/html_report.py`)
- **评分明细表** `_build_score_table()` — 指标/信号/得分列，跳过零分项
- **小白技术解读** `_build_beginner_explanations()` — 卡片网格，RSI/MACD/KDJ/成交量/均线/布林带通俗比喻
- **关键价位表** `_build_key_prices_table()` — 止损/支撑/阻力/目标价格 + 颜色编码
- **操作建议区** `_build_action_advice()` — 根据 action/confidence 给出策略步骤 + 理由列表

### 改进: 报告结构重排
- 结论在前、图表在后：仪表盘 → 价格卡片 → 评分明细 → 小白解读 → 价位表 → 操作建议 → 图表
- 用户一眼就能看到买卖结论和理由，图表作为补充验证

### 文件变更
| 文件 | 操作 |
|------|------|
| `scripts/beginner_analyzer.py` | 修改 TradingSignal + score_breakdown 收集 |
| `scripts/html_report.py` | Toggle工具栏 + 4个新方法 + 报告结构重排 |
| `SKILL.md` | 更新 v4.2 |
| `references/changelog.md` | 更新 |

---

## v4.1.0 (2026-02-24) — 图表可视化升级

### 新增: 可视化数据函数 (`scripts/indicators.py`)
- `find_swing_points()` — 识别 Swing 高低点并返回日期/价格坐标
- `calculate_trend_lines()` — 连接 swing 点计算上升/下降趋势线 + 通道类型（ascending/descending/converging/sideways）
- `calculate_sr_zones()` — 将支撑阻力价格扩展为 ATR×0.3 宽度的色带区域
- `analyze_stock_local()` 返回值新增 `visualization` 字段

### 升级: HTML 报告引擎 (`scripts/html_report.py`)
- **图例系统**: 主图 + 成交量 + MACD + RSI 四图均添加颜色图例
- **支撑阻力色带**: Canvas overlay 半透明矩形区域（绿色支撑/红色阻力），跟随缩放重绘
- **Swing 标注**: K线上标注 swing high/low 价格标签（circle marker）
- **趋势线**: LineSeries 连接最近两个 swing 点绘制上升/下降趋势线
- **布林带填充**: AreaSeries 替代 LineSeries，上下轨间填充半透明色
- **PriceLine API**: 替代 LineSeries 画 S/R 水平线，Y轴显示价格标签 + Fib 标题
- **趋势方向徽章**: 图表标题旁显示 ▲上升趋势/▼下降趋势/◆收敛/─横盘
- **MACD 零轴**: 灰色虚线标注零轴参考线
- **RSI 中线**: 新增 50 中性线，30/50/70 三条参考线

### 文件变更
| 文件 | 操作 |
|------|------|
| `scripts/indicators.py` | 追加 3 个函数 + 修改 `analyze_stock_local()` |
| `scripts/html_report.py` | 全面升级图表渲染 |
| `SKILL.md` | 更新 v4.1 |
| `references/changelog.md` | 更新 |

---

## v4.0.0 (2026-02-24) — 交互式可视化报告

### 新增: HTML 报告引擎 (`scripts/html_report.py`)
- 自包含 HTML 文件，使用 TradingView Lightweight Charts v4 (CDN, Apache 2.0)
- 暗色主题，K 线图 + MA5/10/20/60 + 布林带 + 支撑阻力水平线
- 成交量/MACD/RSI 子图，四图联动缩放
- 评分仪表盘 (-10 ~ +10 SVG 弧形表盘)
- 买卖建议价格卡片（买入/止损/止盈/风险收益比/仓位）
- "在 TradingView 中打开" 跳转按钮
- 支持港股/A股 ticker 到 TradingView symbol 自动映射

### 新增: HTML 报告入口 (`beginner_analyzer.py`)
- `generate_html_report()` 函数：生成 HTML 报告，失败自动回退 Markdown
- 不修改任何已有函数，追加在文件末尾

### 新增: Polymarket 预留接口
- HTML 报告中预留 Polymarket 情绪模块区域
- `generate_html_report()` 接受可选 `polymarket_data` 参数

### 更新: SKILL.md
- 版本号升至 v4.0
- 新增"HTML 可视化报告"章节
- 执行步骤第 6 步更新为默认生成 HTML

### 文件变更
| 文件 | 操作 |
|------|------|
| `scripts/html_report.py` | 新增 |
| `scripts/beginner_analyzer.py` | 末尾追加 `generate_html_report()` |
| `SKILL.md` | 更新 v4.0 |
| `references/changelog.md` | 更新 |

---

## v3.7.0 (2026-02-21) — EvoMap Capsule 融合

通过 EvoMap 协作进化市场获取经过验证的 Capsule 策略，融入 stock-master 工作流。

### 新增: API 容错策略
**来源**: EvoMap Capsule — HTTP Retry + Circuit Breaker (GDI 70.9, 置信度 0.96)

- Alpha Vantage MCP 调用失败时：等 2s 重试 1 次 → 仍失败自动降级到本地计算
- 识别 429/限流响应：标记当天已限流，后续分析直接走本地计算
- Yahoo Finance 超时：重试 2 次（指数退避 2s → 4s），仍失败报错说明原因
- 降级时报告注明数据来源

### 新增: 异常量价信号检测
**来源**: EvoMap Capsule — Median Anomaly Detection (GDI 68.9, 置信度 0.95)

- 放量异常：当日成交量 > 20日中位数 × 3 → "有大资金进场"
- 缩量异常：当日成交量 < 20日中位数 × 0.3 → "市场观望"
- 波动异常：当日涨跌幅 > 20日振幅中位数 × 3 → "波动剧烈，注意风险"
- 数据不足 20 日或中位数为 0 时自动跳过
- 异常信号仅作提醒，不参与评分

### 新增: 多股并行分析
**来源**: EvoMap Capsule — Swarm Task Decomposition (GDI 67.75, 置信度 0.98)

- 2 只股票串行分析
- 3 只及以上使用 Task 工具并行派发子 Agent
- 汇总时统一格式：评分 + 关键指标 + 异常信号，生成对比表格

### 新增: 飞书同步降级链
**来源**: EvoMap Capsule — Format Fallback Chain (置信度 0.91-0.95)

- 富文本写入 → 失败 → 降级纯文本 → 仍失败 → 本地 JSON 备份
- 飞书 API 返回 400 时自动将 markdown 转纯文本重试
- 连续 3 次失败触发熔断，数据备份到 `feishu_sync_backup.json`

---

## v3.6.0 (2026-01-25) — 投资智慧模块

### 新增: 投资智慧佐证系统
- 整理用户个人投资感悟，形成结构化智慧库
- 内容涵盖：股民十大境界、交易核心原则、技术分析智慧、心态与纪律、人生哲学
- 在买卖建议中自动引用相关智慧作为佐证
- 用户迷茫或亏损时引用"十大境界"帮助定位和鼓励
- 新增 `references/investment-wisdom.md` 智慧库文件
- 源文件：`股票交易智慧精粹.docx`（用户可持续更新）

---

## v3.5.0 (2026-01-22) — 飞书多维表格集成

### 新增: 飞书同步
- 支持将分析结果同步到飞书多维表格
  - 技术信号表：股票分析结果、评分、买卖建议
  - 持仓管理表：持仓记录、成本、盈亏
  - 交易记录表：买卖历史、触发信号
- 单向同步架构：本地分析 → 飞书（飞书为主库，避免冲突）
- 自动表结构初始化：`feishu_init_tables.py` 一键创建

### 新增文件
- `scripts/feishu_sync.py` — 飞书 API 封装
- `scripts/feishu_init_tables.py` — 表结构初始化

---

## v3.4.1 (2026-01-22) — 更名

- **重命名**: stock-analyzer → stock-master
- **路径变更**: Excel 默认存储改为 `/Users/liyanda/Desktop/AI编程/stock master/`

---

## v3.4.0 (2026-01-22) — K线形态 + 趋势形态识别

### 新增: K线形态识别
- 单K线：十字星、锤子线、上吊线、射击之星、倒锤子
- 双K线：看涨吞没、看跌吞没
- 三K线：早晨之星、黄昏之星、三只白兵、三只乌鸦

### 新增: 趋势形态识别
- 反转形态：双底(W底)、双顶(M头)、头肩顶、头肩底
- 整理形态：上升三角形、下降三角形、对称三角形

### 改进: 评分系统
- 形态信号纳入评分体系
- 强形态（头肩、双底双顶、三只白兵/乌鸦）±3 分
- 中等形态（吞没、三角形）±2 分
- 弱形态（锤子线、十字星）±1 分

### 新增函数
- `identify_candlestick_patterns()` — K线形态识别
- `identify_chart_patterns()` — 趋势形态识别
- `analyze_patterns()` — 综合形态分析
- `explain_patterns_simple()` — 形态小白解读

---

## v3.3.0 (2026-01-22) — 指标大全

### 新增指标
- **KDJ 随机指标**: 国内股民最常用短线指标，金叉/死叉/超买超卖
- **MACD/RSI 背离检测**: 自动检测顶背离和底背离（权重最高 ±4 分）
- **OBV 量能指标**: 能量潮分析，检测资金流向
- **威廉指标 Williams %R**: 短期超买超卖判断
- **乖离率 BIAS**: 股价偏离均线程度分析

### 改进: 支撑阻力位
- 斐波那契回撤位 + 扩展位 + 整数关口

### 改进: 评分与止损
- 评分阈值调整，背离信号权重最高
- 止损止盈结合支撑阻力位优化

---

## v3.2.0 (2026-01-21) — 港股支持 + 风控体系

### 新增: 港股本地计算
- 自动检测港股代码（.HK 后缀）
- 使用 Yahoo Finance 数据本地计算全部指标

### 新增: 风控工具
- **ATR 动态止损**: 根据波动性自动调整止损距离
- **成交量分析**: 量价配合（放量/缩量 + 涨跌）
- **均线系统**: MA5/10/20/60 + 多空排列判断
- **仓位建议**: 高信号 30% / 中信号 20% / 低信号 10%
- **风险收益比**: 自动计算，默认目标 2.5:1

### 新增: 优雅降级
- Alpha Vantage API 失败时自动回退到本地计算

### 新增文件
- `scripts/indicators.py` — 本地指标计算模块

---

## v3.1.0 (2026-01-21) — 持仓增强

- 新增「交易建议」工作表自动生成
- 每次持仓分析后自动更新买卖点位到 Excel
- 新增 `update_trading_recommendations()` 函数
- 优化做T操作填写说明

---

## v3.0.0 (2026-01-21) — 小白友好化

**里程碑版本** — 从技术工具转型为面向普通投资者的分析助手。

- 新增小白友好分析语言（通俗比喻解释指标）
- 新增买卖点价格建议
- 新增 Excel 持仓管理
- 新增持仓分析功能
- 支持简洁版/详细版报告

---

## v2.0.0 (2026-01-20) — 混合数据源架构

- 接入 Alpha Vantage MCP 获取专业技术指标
- 混合数据源：Yahoo Finance（价格）+ Alpha Vantage（指标）
- 数据源验证机制

---

## v1.0.0 (2025-10-23) — 初始版本

- 基础股票分析功能
- 初始框架搭建
