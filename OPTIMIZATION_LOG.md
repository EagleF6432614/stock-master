# Stock Master SKILL.md 优化记录

## 优化版本：v4.5 → v4.6

**优化日期**：2026-03-13
**优化方法**：基于 skill-creator 方法论，3 轮 Eval+Iterate 循环

---

## 优化目标

将 SKILL.md 从硬编排（step-by-step）改为约束声明式（constraint-based），让 AI 自行决定最佳呈现方式，同时确保数据结构文档完整准确，消除 API 调用歧义。

## 三轮迭代详情

### Round 1：结构性审查

**评估维度与得分：**

| 维度 | 评分 | 问题 |
|------|------|------|
| 触发准确性 | 7/10 | "给个小白版建议"无股票关键词可能不触发 |
| 脚本 API 文档 | 4/10 | `generate_trading_recommendation()` 参数未文档化 |
| 数据结构清晰度 | 3/10 | `analyze_stock_local()` 返回值嵌套结构完全缺失 |
| 约束完整性 | 6/10 | 缺少错误处理、指标冲突、货币单位等 |
| 评分体系 | 8/10 | 表格清晰，缺少指标缺失规则 |
| 场景覆盖 | 7/10 | 场景 C 依赖关系未说明 |

**修复内容：**
1. 补充 `analyze_stock_local()` 完整返回值结构（嵌套 key + 类型标注）
2. 补充 `generate_trading_recommendation()` 完整参数映射代码
3. 新增错误处理约束（ticker 无效、数据不足、单指标失败）
4. 优化 description 触发词覆盖（增加代码模式、公司名、上下文感知）
5. 标注场景 B/C 对场景 A 的依赖关系
6. 新增货币单位约束、指标缺失评分规则

### Round 2：实际测试验证

**测试方法**：启动 2 个独立 subagent，分别用 TSLA（美股）和 688028.SS（A股）执行完整数据流。

**测试结果：**

| 测试项 | TSLA | 688028.SS |
|--------|------|-----------|
| `analyze_stock_local()` 调用 | ✅ 成功 | ✅ 成功 |
| 参数映射一次通过 | ✅ | ✅ |
| `generate_trading_recommendation()` 调用 | ✅ 成功 | ✅ 成功 |
| 最终评分 | 2 (HOLD) | 1 (HOLD) |

**发现的文档 bug（两个测试一致）：**

| Bug | 文档值 | 实际值 | 严重度 |
|-----|--------|--------|--------|
| `bias` key 名 | `bias5/bias10/bias20` | `bias6/bias12/bias24` | 高（KeyError） |
| `divergence` 值 | `str\|None` | `'none'` 字符串 | 中（类型误导） |
| `score_breakdown` 类型 | `dict` | `list[dict]` | 中（接口不匹配） |
| `TradingSignal` 属性 | 7 个 | 实际 22 个 | 低（信息缺失） |

**修复内容：**
1. `bias` keys 修正为 `bias6/bias12/bias24`
2. `divergence` 类型标注为 `str`，注明 `'none'` 是字符串
3. `score_breakdown` 修正为 `list[dict]`，标注元素结构
4. 补充 `TradingSignal` 关键属性（`buy_price`, `sell_price`, `confidence`, `risk_reward_ratio`）

### Round 3：回归验证

**结果：8/8 全部通过**

| 检查项 | 结果 |
|--------|------|
| `bias` key 名修正 | ✅ PASS |
| `divergence` 类型修正 | ✅ PASS |
| `score_breakdown` 类型修正 | ✅ PASS |
| `TradingSignal` 属性补充 | ✅ PASS |
| 总行数 < 500 | ✅ 287 行 |
| 数据结构无需读源码 | ✅ PASS |
| 无歧义无矛盾 | ✅ PASS |
| 触发词覆盖 7 种场景 | ✅ PASS |

## 代码 Bug 修复（附带）

### 1. RSI 初始化 Bug（`scripts/indicators.py`）

**问题**：`calculate_rsi()` 使用 `avg_gain = gains[0]`（单值初始化），而标准 Wilder 方法应使用前 N 期的 SMA。

**修复**：
```python
# Before
avg_gain = gains[0]
avg_loss = losses[0]
for i in range(1, len(gains)):

# After
avg_gain = np.mean(gains[:period])
avg_loss = np.mean(losses[:period])
for i in range(period, len(gains)):
```

### 2. 评分溢出 Bug（`scripts/beginner_analyzer.py`）

**问题**：`generate_trading_recommendation()` 的 `buy_score` 可能超出 [-10, +10] 范围。

**修复**：在 action 判断前添加截断：
```python
buy_score = max(-10, min(10, buy_score))
```

## SKILL.md 设计哲学变更

### Before (v4.5 之前)：硬编排式
```markdown
执行步骤：
1. 获取数据
2. 计算 RSI，如果 < 30 则...
3. 格式化输出为：
   ### 技术分析
   #### RSI 指标
   ...
```

### After (v4.6)：约束声明式
```markdown
执行：获取数据 → 计算全部指标 → 生成评分 → 输出文字分析 + HTML 报告。
AI 自行决定最佳呈现方式，但必须满足上述输出质量约束。
```

核心变化：
- 不规定输出格式，只规定质量约束（结论先行、可执行、风险对称、小白友好、数据透明、风险提示）
- 不规定分析步骤，只提供数据结构和参数映射
- 场景用触发条件 + 额外约束声明，不用步骤编号

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `SKILL.md` | 重写 | v4.5→v4.6，约束声明式 + 完整数据结构 + 错误处理 |
| `scripts/indicators.py` | Bug fix | RSI 初始化修复（Wilder SMA 标准） |
| `scripts/beginner_analyzer.py` | Bug fix | 评分 [-10,+10] 截断 |
