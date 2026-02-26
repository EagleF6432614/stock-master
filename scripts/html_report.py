"""
HTML 可视化报告生成模块 v4.2

功能:
- 生成自包含的交互式 HTML 分析报告
- 使用 TradingView Lightweight Charts (CDN, Apache 2.0)
- K线图 + MA/布林带填充/支撑阻力区域带 叠加层
- Swing 高低点标注 + 趋势线 + 趋势方向标签
- 成交量/MACD/RSI 子图（联动缩放 + 图例 + 参考线）
- 评分仪表盘 + 买卖建议卡片
- "在 TradingView 中打开" 跳转按钮
- 可选 Polymarket 情绪模块

v4.1:
- 图例标注所有线条含义
- 支撑阻力区域带（半透明色带替代细线）
- Swing 高低点价格标注
- 趋势线（连接 swing 点）
- 布林带填充效果
- PriceLine API 替代 LineSeries 水平线
- 趋势方向标签
- MACD 零轴 + RSI 50 中性线 + 子图图例

v4.2:
- 综合评分表（score_breakdown 明细）
- 小白友好技术指标解读（生动比喻）
- 关键价位表（止损/支撑/阻力/目标位）
- 操作建议模块（分仓策略 + 分析理由）
- 文字分析移至图表前面（先看结论再看图）
- 图表叠加层切换工具栏（MA/BB/SR/Swing/趋势线/斐波那契）
"""

import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
import numpy as np


LIGHTWEIGHT_CHARTS_CDN = (
    "https://unpkg.com/lightweight-charts@4/dist/"
    "lightweight-charts.standalone.production.js"
)

# TradingView 跳转 URL 模板
TV_URL_TEMPLATE = "https://www.tradingview.com/chart/?symbol={symbol}"

# 报告输出目录
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Desktop/AI编程/stock master/reports")


def _format_date(dt) -> str:
    """将 pandas Timestamp 或 datetime 转为 'YYYY-MM-DD' 字符串"""
    if hasattr(dt, 'strftime'):
        return dt.strftime('%Y-%m-%d')
    return str(dt)[:10]


def _ticker_to_tv_symbol(ticker: str) -> str:
    """将 yfinance ticker 转换为 TradingView symbol 格式"""
    t = ticker.upper()
    if t.endswith('.HK'):
        num = t.replace('.HK', '')
        return f"HKEX:{num}"
    elif t.endswith('.SS'):
        return f"SSE:{t.replace('.SS', '')}"
    elif t.endswith('.SZ'):
        return f"SZSE:{t.replace('.SZ', '')}"
    else:
        return t  # TradingView 搜索对纯 ticker 有良好兼容


class HTMLReportGenerator:
    """自包含 HTML 报告生成器"""

    def generate(
        self,
        ticker: str,
        name: str,
        analysis_result: Dict[str, Any],
        signal,  # TradingSignal dataclass
        stock_data: Dict[str, Any],
        polymarket_data: Optional[Dict[str, Any]] = None,
        report_type: str = 'detailed'
    ) -> str:
        """
        生成 HTML 报告并保存到文件。

        返回: HTML 文件绝对路径
        """
        indicators = analysis_result.get('indicators', {})
        sr = analysis_result.get('support_resistance', {})
        patterns = analysis_result.get('patterns', {})
        divergence = analysis_result.get('divergence', {})
        stop_loss_data = analysis_result.get('stop_loss', {})
        visualization = analysis_result.get('visualization', {})

        # 提取原始数据
        dates = stock_data.get('dates', [])
        close = np.array(stock_data.get('close', []))
        high = np.array(stock_data.get('high', []))
        low = np.array(stock_data.get('low', []))
        open_prices = np.array(stock_data.get('open', []))
        volume = np.array(stock_data.get('volume', []))

        if len(dates) == 0:
            raise ValueError("stock_data 中无日期数据")

        # 格式化日期
        date_strs = [_format_date(d) for d in dates]
        # 去重（yfinance 偶尔有重复行）
        seen = set()
        unique_indices = []
        for i, ds in enumerate(date_strs):
            if ds not in seen:
                seen.add(ds)
                unique_indices.append(i)

        date_strs = [date_strs[i] for i in unique_indices]
        close = close[unique_indices]
        high = high[unique_indices]
        low = low[unique_indices]
        open_prices = open_prices[unique_indices]
        volume = volume[unique_indices]

        current_price = analysis_result.get('current_price', float(close[-1]))

        # 计算涨跌幅
        if len(close) >= 2:
            change = close[-1] - close[-2]
            change_pct = change / close[-2] * 100
        else:
            change = 0
            change_pct = 0

        # 构建各部分数据
        ohlcv_js = self._build_ohlcv_js(date_strs, open_prices, high, low, close)
        volume_js = self._build_volume_js(date_strs, volume, close)
        ma_js = self._build_ma_js(date_strs, close)
        bb_js = self._build_bollinger_js(date_strs, close)
        sr_js = self._build_sr_js(date_strs, sr)
        macd_js = self._build_macd_js(date_strs, close)
        rsi_js = self._build_rsi_js(date_strs, close)
        # v4.1: 新可视化数据
        swing_js = self._build_swing_js(visualization.get('swing_points', []))
        trend_js = self._build_trend_lines_js(visualization.get('trend_lines', {}))
        sr_zones_js = self._build_sr_zones_js(visualization.get('sr_zones', []))
        markers_js = self._build_markers_js(
            date_strs, patterns, visualization.get('swing_points', [])
        )
        # 趋势方向
        trend_lines_data = visualization.get('trend_lines', {})
        channel_type = trend_lines_data.get('channel_type', 'sideways') if trend_lines_data else 'sideways'

        # 构建 HTML
        tv_symbol = _ticker_to_tv_symbol(ticker)
        tv_url = TV_URL_TEMPLATE.format(symbol=tv_symbol)

        score = getattr(signal, 'score', None)
        # 从 signal 推断分数（score 可能为 None）
        if score is None or score == 0:
            action = getattr(signal, 'action', 'HOLD')
            confidence = getattr(signal, 'confidence', '中')
            if action == 'BUY':
                score = 6 if confidence == '高' else 4
            elif action == 'STRONG_BUY':
                score = 8
            elif action == 'SELL':
                score = -6 if confidence == '高' else -4
            elif action == 'STRONG_SELL':
                score = -8
            else:
                score = 0

        trend_badge_html = self._build_trend_badge(channel_type, indicators.get('ma_system', {}))
        gauge_html = self._build_gauge(score, signal)
        price_cards_html = self._build_price_cards(signal, current_price)
        # v4.2: 新分析组件（替代旧 analysis_html）
        score_table_html = self._build_score_table(signal)
        beginner_html = self._build_beginner_explanations(indicators)
        key_prices_html = self._build_key_prices_table(signal, sr)
        action_advice_html = self._build_action_advice(signal)
        wisdom_html = self._build_wisdom_section(signal)
        polymarket_html = self._build_polymarket_section(polymarket_data)
        disclaimer_html = self._build_disclaimer()

        change_sign = '+' if change_pct >= 0 else ''
        change_color = '#26a69a' if change_pct >= 0 else '#ef5350'

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{ticker.upper()} 技术分析 - Stock Master v4.2</title>
    <script src="{LIGHTWEIGHT_CHARTS_CDN}"></script>
    <style>{self._get_css()}</style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-left">
                <h1>{ticker.upper()}</h1>
                <span class="stock-name">{name}</span>
                <span class="price" style="color:{change_color}">
                    ${current_price:.2f}
                    <span class="change">{change_sign}{change_pct:.2f}%</span>
                </span>
            </div>
            <div class="header-right">
                <a href="{tv_url}" target="_blank" class="tv-button">
                    <svg width="20" height="20" viewBox="0 0 36 28" fill="none">
                        <path d="M14 22H7V11H0V4h14v18zm8-18h-7v18h7V14h7v-4h-7V4z" fill="currentColor"/>
                    </svg>
                    在 TradingView 中打开
                </a>
                <div class="timestamp">{analysis_result.get('timestamp', '')[:19]}</div>
            </div>
        </div>

        <!-- 评分仪表盘 -->
        {gauge_html}

        <!-- 价格卡片 -->
        {price_cards_html}

        <!-- v4.2: 文字分析（在图表前面） -->
        {score_table_html}
        {beginner_html}
        {key_prices_html}
        {action_advice_html}
        {wisdom_html}

        <!-- K线主图 -->
        <div class="section-card">
            <!-- v4.2: 图表切换工具栏 -->
            <div class="chart-toggles">
                <button class="toggle-btn active" data-group="ma">均线</button>
                <button class="toggle-btn" data-group="bb">布林带</button>
                <button class="toggle-btn" data-group="sr">支撑阻力</button>
                <button class="toggle-btn" data-group="swing">Swing标注</button>
                <button class="toggle-btn" data-group="trend">趋势线</button>
                <button class="toggle-btn" data-group="fib">斐波那契</button>
            </div>
            <div class="chart-header">
                <h2>K线图 · 技术叠加</h2>
                {trend_badge_html}
            </div>
            <div id="chart-main-wrapper" style="position:relative">
                <div id="chart-main" class="chart-container"></div>
                <canvas id="sr-overlay" style="position:absolute;top:0;left:0;pointer-events:none;"></canvas>
            </div>
            <div class="chart-legend-bar">
                <span class="legend-item"><span class="legend-line" style="background:#f7c948"></span>MA5</span>
                <span class="legend-item"><span class="legend-line" style="background:#42a5f5"></span>MA10</span>
                <span class="legend-item"><span class="legend-line" style="background:#ab47bc"></span>MA20</span>
                <span class="legend-item"><span class="legend-line" style="background:#ff7043"></span>MA60</span>
                <span class="legend-item"><span class="legend-line legend-dashed" style="background:#90a4ae"></span>布林带</span>
                <span class="legend-item"><span class="legend-block" style="background:rgba(38,166,154,0.2)"></span>支撑区</span>
                <span class="legend-item"><span class="legend-block" style="background:rgba(239,83,80,0.2)"></span>阻力区</span>
                <span class="legend-item"><span class="legend-dot" style="background:#ef5350"></span>Swing High</span>
                <span class="legend-item"><span class="legend-dot" style="background:#26a69a"></span>Swing Low</span>
                <span class="legend-item"><span class="legend-line" style="background:#26a69a"></span>上升趋势线</span>
                <span class="legend-item"><span class="legend-line" style="background:#ef5350"></span>下降趋势线</span>
            </div>
        </div>

        <!-- 成交量 -->
        <div class="section-card">
            <h2>成交量</h2>
            <div id="chart-volume" class="chart-container-sm"></div>
            <div class="chart-legend-bar sub-legend">
                <span class="legend-item"><span class="legend-block" style="background:#26a69a80"></span>上涨量</span>
                <span class="legend-item"><span class="legend-block" style="background:#ef535080"></span>下跌量</span>
            </div>
        </div>

        <!-- MACD -->
        <div class="section-card">
            <h2>MACD</h2>
            <div id="chart-macd" class="chart-container-sm"></div>
            <div class="chart-legend-bar sub-legend">
                <span class="legend-item"><span class="legend-block" style="background:#26a69a"></span>多方柱</span>
                <span class="legend-item"><span class="legend-block" style="background:#ef5350"></span>空方柱</span>
                <span class="legend-item"><span class="legend-line" style="background:#42a5f5"></span>MACD线</span>
                <span class="legend-item"><span class="legend-line" style="background:#ff7043"></span>信号线</span>
                <span class="legend-item"><span class="legend-line legend-dashed" style="background:#555"></span>零轴</span>
            </div>
        </div>

        <!-- RSI -->
        <div class="section-card">
            <h2>RSI</h2>
            <div id="chart-rsi" class="chart-container-sm"></div>
            <div class="chart-legend-bar sub-legend">
                <span class="legend-item"><span class="legend-line" style="background:#ab47bc"></span>RSI(14)</span>
                <span class="legend-item"><span class="legend-line legend-dashed" style="background:#26a69a44"></span>超卖(30)</span>
                <span class="legend-item"><span class="legend-line legend-dashed" style="background:#888"></span>中性(50)</span>
                <span class="legend-item"><span class="legend-line legend-dashed" style="background:#ef535044"></span>超买(70)</span>
            </div>
        </div>

        <!-- Polymarket 情绪 -->
        {polymarket_html}

        <!-- 免责声明 -->
        {disclaimer_html}

        <div class="footer">
            Stock Master v4.2 · Powered by Lightweight Charts
        </div>
    </div>

    <script>
    // ===== 数据 =====
    {ohlcv_js}
    {volume_js}
    {ma_js}
    {bb_js}
    {sr_js}
    {macd_js}
    {rsi_js}
    {markers_js}
    {swing_js}
    {trend_js}
    {sr_zones_js}

    // ===== 工具函数 =====
    function createChart(containerId, height) {{
        const container = document.getElementById(containerId);
        return LightweightCharts.createChart(container, {{
            width: container.offsetWidth,
            height: height,
            layout: {{
                background: {{ type: 'solid', color: '#1a1a2e' }},
                textColor: '#a0a0b0',
                fontSize: 12,
            }},
            grid: {{
                vertLines: {{ color: '#2a2a3e' }},
                horzLines: {{ color: '#2a2a3e' }},
            }},
            crosshair: {{
                mode: LightweightCharts.CrosshairMode.Normal,
            }},
            rightPriceScale: {{
                borderColor: '#2a2a3e',
            }},
            timeScale: {{
                borderColor: '#2a2a3e',
                timeVisible: false,
            }},
        }});
    }}

    // ===== 主图 =====
    const mainChart = createChart('chart-main', 420);
    const candleSeries = mainChart.addCandlestickSeries({{
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderUpColor: '#26a69a',
        borderDownColor: '#ef5350',
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
    }});
    candleSeries.setData(ohlcvData);

    // 买卖信号 + Swing 高低点 markers（合并）
    if (typeof markerData !== 'undefined' && markerData.length > 0) {{
        candleSeries.setMarkers(markerData);
    }}

    // v4.2: Series group tracking for toggle toolbar
    const seriesGroups = {{ ma: [], bb: [], sr: [], swing: [], trend: [], fib: [] }};
    const priceLineConfigs = {{ sr: [], fib: [] }};
    const priceLineRefs = {{ sr: [], fib: [] }};
    const originalMarkers = (typeof markerData !== 'undefined') ? markerData : [];

    // MA 线
    const maColors = {{ ma5: '#f7c948', ma10: '#42a5f5', ma20: '#ab47bc', ma60: '#ff7043' }};
    for (const [key, data] of Object.entries(maSeriesData)) {{
        if (data.length > 0) {{
            const s = mainChart.addLineSeries({{
                color: maColors[key] || '#888',
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
            }});
            s.setData(data);
            seriesGroups.ma.push(s);
        }}
    }}

    // 布林带（v4.1: 填充效果 — 上轨+下轨用 AreaSeries，中轨用 LineSeries）
    if (typeof bbData !== 'undefined') {{
        const bbCommon = {{ priceLineVisible: false, lastValueVisible: false }};
        if (bbData.upper.length > 0) {{
            const bbUpper = mainChart.addAreaSeries({{
                ...bbCommon,
                topColor: 'rgba(144, 164, 174, 0.12)',
                bottomColor: 'rgba(144, 164, 174, 0.02)',
                lineColor: 'rgba(144, 164, 174, 0.45)',
                lineWidth: 1,
                lineStyle: 2,
            }});
            bbUpper.setData(bbData.upper);
            seriesGroups.bb.push(bbUpper);
        }}
        if (bbData.middle.length > 0) {{
            const bbMid = mainChart.addLineSeries({{
                ...bbCommon,
                color: '#546e7a',
                lineWidth: 1,
            }});
            bbMid.setData(bbData.middle);
            seriesGroups.bb.push(bbMid);
        }}
        if (bbData.lower.length > 0) {{
            const bbLower = mainChart.addAreaSeries({{
                ...bbCommon,
                topColor: 'rgba(144, 164, 174, 0.02)',
                bottomColor: 'rgba(144, 164, 174, 0.12)',
                lineColor: 'rgba(144, 164, 174, 0.45)',
                lineWidth: 1,
                lineStyle: 2,
            }});
            bbLower.setData(bbData.lower);
            seriesGroups.bb.push(bbLower);
        }}
    }}

    // 支撑阻力 — v4.1: PriceLine API（Y轴标签）+ v4.2: 存储 refs 用于 toggle
    if (typeof srLines !== 'undefined') {{
        for (const line of srLines) {{
            if (line.data && line.data.length > 0) {{
                const price = line.data[0].value;
                const label = line.label || '';
                const config = {{
                    price: price,
                    color: line.color,
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: label,
                }};
                const ref = candleSeries.createPriceLine(config);
                const group = line.group || (label.startsWith('Fib') ? 'fib' : 'sr');
                priceLineConfigs[group].push(config);
                priceLineRefs[group].push(ref);
            }}
        }}
    }}

    // v4.1: 趋势线
    if (typeof trendLinesData !== 'undefined') {{
        if (trendLinesData.upper_trend) {{
            const ut = trendLinesData.upper_trend;
            const utSeries = mainChart.addLineSeries({{
                color: ut.direction === 'down' ? '#ef5350' : '#26a69a',
                lineWidth: 2,
                lineStyle: 0,
                priceLineVisible: false,
                lastValueVisible: false,
            }});
            utSeries.setData([
                {{ time: ut.start.date, value: ut.start.price }},
                {{ time: ut.end.date, value: ut.end.price }},
            ]);
            seriesGroups.trend.push(utSeries);
        }}
        if (trendLinesData.lower_trend) {{
            const lt = trendLinesData.lower_trend;
            const ltSeries = mainChart.addLineSeries({{
                color: lt.direction === 'up' ? '#26a69a' : '#ef5350',
                lineWidth: 2,
                lineStyle: 0,
                priceLineVisible: false,
                lastValueVisible: false,
            }});
            ltSeries.setData([
                {{ time: lt.start.date, value: lt.start.price }},
                {{ time: lt.end.date, value: lt.end.price }},
            ]);
            seriesGroups.trend.push(ltSeries);
        }}
    }}

    // v4.1: S/R 区域带 Canvas overlay
    let srZonesVisible = true;
    let drawZones = function() {{}};
    (function() {{
        const wrapper = document.getElementById('chart-main-wrapper');
        const canvas = document.getElementById('sr-overlay');
        if (!wrapper || !canvas || typeof srZonesData === 'undefined' || srZonesData.length === 0) return;

        function resizeCanvas() {{
            canvas.width = wrapper.offsetWidth;
            canvas.height = wrapper.offsetHeight;
        }}

        drawZones = function() {{
            resizeCanvas();
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (!srZonesVisible) return;

            for (const zone of srZonesData) {{
                const y1 = candleSeries.priceToCoordinate(zone.upper);
                const y2 = candleSeries.priceToCoordinate(zone.lower);
                if (y1 === null || y2 === null) continue;

                const isSupport = zone.type === 'support';
                ctx.fillStyle = isSupport
                    ? 'rgba(38, 166, 154, 0.10)'
                    : 'rgba(239, 83, 80, 0.10)';
                ctx.fillRect(0, Math.min(y1, y2), canvas.width, Math.abs(y2 - y1));

                // 区域标签
                ctx.fillStyle = isSupport ? 'rgba(38, 166, 154, 0.6)' : 'rgba(239, 83, 80, 0.6)';
                ctx.font = '10px sans-serif';
                ctx.fillText(zone.label, 8, Math.min(y1, y2) + 12);
            }}
        }};

        drawZones();
        mainChart.timeScale().subscribeVisibleLogicalRangeChange(drawZones);
        window.addEventListener('resize', () => {{ setTimeout(drawZones, 150); }});
    }})();

    // ===== 成交量图 =====
    const volChart = createChart('chart-volume', 120);
    const volSeries = volChart.addHistogramSeries({{
        priceFormat: {{ type: 'volume' }},
        priceScaleId: '',
    }});
    volSeries.setData(volumeData);

    // ===== MACD 图 =====
    const macdChart = createChart('chart-macd', 150);
    const macdHistSeries = macdChart.addHistogramSeries({{
        priceLineVisible: false,
    }});
    macdHistSeries.setData(macdHistogramData);

    const macdLineSeries = macdChart.addLineSeries({{
        color: '#42a5f5',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
    }});
    macdLineSeries.setData(macdLineData);

    const signalLineSeries = macdChart.addLineSeries({{
        color: '#ff7043',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
    }});
    signalLineSeries.setData(signalLineData);

    // v4.1: MACD 零轴
    if (macdLineData.length > 0) {{
        const macdZero = macdChart.addLineSeries({{
            color: '#555',
            lineWidth: 1,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
        }});
        macdZero.setData([
            {{ time: macdLineData[0].time, value: 0 }},
            {{ time: macdLineData[macdLineData.length-1].time, value: 0 }},
        ]);
    }}

    // ===== RSI 图 =====
    const rsiChart = createChart('chart-rsi', 120);
    const rsiSeries = rsiChart.addLineSeries({{
        color: '#ab47bc',
        lineWidth: 2,
        priceLineVisible: false,
    }});
    rsiSeries.setData(rsiData);

    // RSI 30/50/70 参考线
    if (rsiData.length > 0) {{
        const rsiFirst = rsiData[0].time;
        const rsiLast = rsiData[rsiData.length-1].time;
        const rsiRefStyle = {{ lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }};

        const rsi30 = rsiChart.addLineSeries({{ ...rsiRefStyle, color: '#26a69a44' }});
        rsi30.setData([{{ time: rsiFirst, value: 30 }}, {{ time: rsiLast, value: 30 }}]);

        const rsi50 = rsiChart.addLineSeries({{ ...rsiRefStyle, color: '#88888844' }});
        rsi50.setData([{{ time: rsiFirst, value: 50 }}, {{ time: rsiLast, value: 50 }}]);

        const rsi70 = rsiChart.addLineSeries({{ ...rsiRefStyle, color: '#ef535044' }});
        rsi70.setData([{{ time: rsiFirst, value: 70 }}, {{ time: rsiLast, value: 70 }}]);
    }}

    // ===== 图表联动 =====
    function syncCharts(master, followers) {{
        master.timeScale().subscribeVisibleLogicalRangeChange(range => {{
            if (range) {{
                followers.forEach(c => c.timeScale().setVisibleLogicalRange(range));
            }}
        }});
    }}
    syncCharts(mainChart, [volChart, macdChart, rsiChart]);
    syncCharts(volChart, [mainChart, macdChart, rsiChart]);

    // ===== 响应式 =====
    const allCharts = [
        {{ chart: mainChart, id: 'chart-main', h: 420 }},
        {{ chart: volChart, id: 'chart-volume', h: 120 }},
        {{ chart: macdChart, id: 'chart-macd', h: 150 }},
        {{ chart: rsiChart, id: 'chart-rsi', h: 120 }},
    ];
    window.addEventListener('resize', () => {{
        allCharts.forEach(({{ chart, id, h }}) => {{
            const w = document.getElementById(id).offsetWidth;
            chart.resize(w, h);
        }});
    }});

    // 初始适配宽度
    setTimeout(() => {{
        allCharts.forEach(({{ chart, id, h }}) => {{
            const w = document.getElementById(id).offsetWidth;
            chart.resize(w, h);
        }});
        mainChart.timeScale().fitContent();
        volChart.timeScale().fitContent();
        macdChart.timeScale().fitContent();
        rsiChart.timeScale().fitContent();
    }}, 100);

    // ===== v4.2: Toggle Toolbar =====
    function toggleGroup(group, visible) {{
        const btn = document.querySelector('.toggle-btn[data-group="' + group + '"]');
        if (btn) btn.classList.toggle('active', visible);

        // LineSeries / AreaSeries toggle
        if (seriesGroups[group]) {{
            seriesGroups[group].forEach(function(s) {{
                try {{ s.applyOptions({{visible: visible}}); }} catch(e) {{}}
            }});
        }}

        // Swing markers toggle
        if (group === 'swing') {{
            if (visible) {{
                candleSeries.setMarkers(originalMarkers);
            }} else {{
                candleSeries.setMarkers(originalMarkers.filter(function(m) {{ return m.shape !== 'circle'; }}));
            }}
        }}

        // PriceLine toggle (remove/recreate approach)
        if (group === 'fib' || group === 'sr') {{
            if (!visible) {{
                priceLineRefs[group].forEach(function(ref) {{
                    try {{ candleSeries.removePriceLine(ref); }} catch(e) {{}}
                }});
                priceLineRefs[group] = [];
            }} else {{
                priceLineConfigs[group].forEach(function(config) {{
                    priceLineRefs[group].push(candleSeries.createPriceLine(config));
                }});
            }}
        }}

        // S/R zones canvas toggle
        if (group === 'sr') {{
            srZonesVisible = visible;
            if (typeof drawZones === 'function') drawZones();
        }}
    }}

    // Wire up buttons
    document.querySelectorAll('.toggle-btn').forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            var group = btn.dataset.group;
            var isActive = btn.classList.contains('active');
            toggleGroup(group, !isActive);
        }});
    }});

    // Default: hide all except MA and K-line
    ['bb', 'sr', 'swing', 'trend', 'fib'].forEach(function(g) {{ toggleGroup(g, false); }});

    </script>
</body>
</html>"""

        # 保存文件
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        filename = f"{ticker.upper()}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
        filepath = os.path.join(DEFAULT_OUTPUT_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        # macOS 自动打开
        try:
            subprocess.Popen(['open', filepath])
        except Exception:
            pass

        return filepath

    # ===== 数据序列化方法 =====

    def _build_ohlcv_js(self, dates, open_p, high, low, close) -> str:
        entries = []
        for i in range(len(dates)):
            entries.append({
                'time': dates[i],
                'open': round(float(open_p[i]), 4),
                'high': round(float(high[i]), 4),
                'low': round(float(low[i]), 4),
                'close': round(float(close[i]), 4),
            })
        return f"const ohlcvData = {json.dumps(entries)};"

    def _build_volume_js(self, dates, volume, close) -> str:
        entries = []
        for i in range(len(dates)):
            color = '#26a69a80' if (i == 0 or close[i] >= close[i-1]) else '#ef535080'
            entries.append({
                'time': dates[i],
                'value': round(float(volume[i]), 0),
                'color': color,
            })
        return f"const volumeData = {json.dumps(entries)};"

    def _build_ma_js(self, dates, close) -> str:
        result = {}
        for period, key in [(5, 'ma5'), (10, 'ma10'), (20, 'ma20'), (60, 'ma60')]:
            series = []
            if len(close) >= period:
                for i in range(period - 1, len(close)):
                    val = float(np.mean(close[i - period + 1:i + 1]))
                    series.append({'time': dates[i], 'value': round(val, 4)})
            result[key] = series
        return f"const maSeriesData = {json.dumps(result)};"

    def _build_bollinger_js(self, dates, close, period=20, std_dev=2.0) -> str:
        upper, middle, lower = [], [], []
        if len(close) >= period:
            for i in range(period - 1, len(close)):
                window = close[i - period + 1:i + 1]
                mid = float(np.mean(window))
                std = float(np.std(window))
                upper.append({'time': dates[i], 'value': round(mid + std_dev * std, 4)})
                middle.append({'time': dates[i], 'value': round(mid, 4)})
                lower.append({'time': dates[i], 'value': round(mid - std_dev * std, 4)})
        return f"const bbData = {json.dumps({'upper': upper, 'middle': middle, 'lower': lower})};"

    def _build_sr_js(self, dates, sr_data) -> str:
        """支撑阻力线（v4.1: 用 PriceLine API，含标签）"""
        lines = []
        if not sr_data or not dates:
            return f"const srLines = {json.dumps(lines)};"

        first_date = dates[0]
        last_date = dates[-1]

        # 斐波那契水平线
        fib = sr_data.get('fibonacci', {})
        for level_name, price in fib.items():
            if price and price > 0:
                lines.append({
                    'color': '#ffd54f66',
                    'label': f'Fib {level_name}',
                    'group': 'fib',
                    'data': [
                        {'time': first_date, 'value': round(float(price), 4)},
                        {'time': last_date, 'value': round(float(price), 4)},
                    ]
                })

        # 支撑位
        for s in sr_data.get('supports', [])[:3]:
            price = s.get('price', 0)
            if price > 0:
                lines.append({
                    'color': '#26a69a88',
                    'label': f"S: {s.get('type', '支撑')}",
                    'group': 'sr',
                    'data': [
                        {'time': first_date, 'value': round(float(price), 4)},
                        {'time': last_date, 'value': round(float(price), 4)},
                    ]
                })

        # 阻力位
        for r in sr_data.get('resistances', [])[:3]:
            price = r.get('price', 0)
            if price > 0:
                lines.append({
                    'color': '#ef535088',
                    'label': f"R: {r.get('type', '阻力')}",
                    'group': 'sr',
                    'data': [
                        {'time': first_date, 'value': round(float(price), 4)},
                        {'time': last_date, 'value': round(float(price), 4)},
                    ]
                })

        return f"const srLines = {json.dumps(lines)};"

    def _build_macd_js(self, dates, close) -> str:
        """计算完整 MACD 序列"""
        if len(close) < 35:  # 26 + 9
            return ("const macdHistogramData = [];\n"
                    "const macdLineData = [];\n"
                    "const signalLineData = [];")

        # EMA 计算
        def ema_series(data, period):
            alpha = 2.0 / (period + 1)
            result = [float(data[0])]
            for i in range(1, len(data)):
                result.append(alpha * float(data[i]) + (1 - alpha) * result[-1])
            return result

        ema12 = ema_series(close, 12)
        ema26 = ema_series(close, 26)
        macd_line = [ema12[i] - ema26[i] for i in range(len(close))]
        signal_line = ema_series(macd_line, 9)
        histogram = [macd_line[i] - signal_line[i] for i in range(len(close))]

        # 从第 34 个数据点开始（确保 EMA 稳定）
        start = 33
        hist_data = []
        ml_data = []
        sl_data = []
        for i in range(start, len(close)):
            h = histogram[i]
            hist_data.append({
                'time': dates[i],
                'value': round(h, 4),
                'color': '#26a69a' if h >= 0 else '#ef5350',
            })
            ml_data.append({'time': dates[i], 'value': round(macd_line[i], 4)})
            sl_data.append({'time': dates[i], 'value': round(signal_line[i], 4)})

        return (f"const macdHistogramData = {json.dumps(hist_data)};\n"
                f"const macdLineData = {json.dumps(ml_data)};\n"
                f"const signalLineData = {json.dumps(sl_data)};")

    def _build_rsi_js(self, dates, close, period=14) -> str:
        """计算完整 RSI 序列"""
        if len(close) < period + 1:
            return "const rsiData = [];"

        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        alpha = 1.0 / period
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        rsi_entries = []
        for i in range(period, len(gains)):
            avg_gain = alpha * float(gains[i]) + (1 - alpha) * avg_gain
            avg_loss = alpha * float(losses[i]) + (1 - alpha) * avg_loss

            if avg_loss == 0:
                rsi_val = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_val = 100 - (100 / (1 + rs))

            # dates 索引偏移：deltas 比 close 少 1 个元素
            date_idx = i + 1
            if date_idx < len(dates):
                rsi_entries.append({
                    'time': dates[date_idx],
                    'value': round(rsi_val, 2)
                })

        return f"const rsiData = {json.dumps(rsi_entries)};"

    def _build_markers_js(self, dates, patterns, swing_points=None) -> str:
        """从形态 + swing 高低点生成 K 线图标记（v4.1）"""
        markers = []

        # Swing 高低点标注价格
        if swing_points:
            for p in swing_points:
                is_high = p['type'] == 'high'
                markers.append({
                    'time': p['date'],
                    'position': 'aboveBar' if is_high else 'belowBar',
                    'color': '#ef5350' if is_high else '#26a69a',
                    'shape': 'circle',
                    'text': f"${p['price']:.2f}",
                })

        # 形态信号标记（最后一根 K 线上）
        last_date = dates[-1] if dates else None
        if patterns and last_date:
            candlestick_patterns = patterns.get('candlestick_patterns', [])
            for p in candlestick_patterns[:3]:
                name = p.get('name', '') if isinstance(p, dict) else str(p)
                is_bullish = p.get('type', '') == 'bullish' if isinstance(p, dict) else False
                markers.append({
                    'time': last_date,
                    'position': 'belowBar' if is_bullish else 'aboveBar',
                    'color': '#26a69a' if is_bullish else '#ef5350',
                    'shape': 'arrowUp' if is_bullish else 'arrowDown',
                    'text': name[:10],
                })

        # 按时间排序（LWC 要求 markers 时间有序）
        markers.sort(key=lambda m: m['time'])
        return f"const markerData = {json.dumps(markers)};"

    def _build_swing_js(self, swing_points) -> str:
        """Swing 点数据（供 JS 使用）"""
        return f"const swingData = {json.dumps(swing_points or [])};"

    def _build_trend_lines_js(self, trend_lines) -> str:
        """趋势线数据"""
        if not trend_lines:
            trend_lines = {'upper_trend': None, 'lower_trend': None, 'channel_type': 'sideways'}
        return f"const trendLinesData = {json.dumps(trend_lines)};"

    def _build_sr_zones_js(self, sr_zones) -> str:
        """S/R 区域带数据"""
        return f"const srZonesData = {json.dumps(sr_zones or [])};"

    def _build_trend_badge(self, channel_type, ma_system) -> str:
        """趋势方向标签"""
        arrangement = ma_system.get('arrangement', '') if ma_system else ''

        # 综合判断趋势
        if channel_type == 'ascending' or arrangement == '多头排列':
            return '<span class="trend-badge bullish">&#9650; 上升趋势</span>'
        elif channel_type == 'descending' or arrangement == '空头排列':
            return '<span class="trend-badge bearish">&#9660; 下降趋势</span>'
        elif channel_type == 'converging':
            return '<span class="trend-badge neutral">&#9670; 收敛整理</span>'
        else:
            return '<span class="trend-badge neutral">&#9644; 横盘整理</span>'

    # ===== HTML 组件 =====

    def _build_gauge(self, score: int, signal) -> str:
        """CSS/SVG 评分仪表盘"""
        # 分数 -10~+10 映射到角度 -90~+90
        clamped = max(-10, min(10, score))
        needle_deg = (clamped / 10) * 90

        action = getattr(signal, 'action', 'HOLD')
        confidence = getattr(signal, 'confidence', '中')

        action_map = {
            'BUY': ('建议买入', '#26a69a'),
            'SELL': ('建议卖出', '#ef5350'),
            'HOLD': ('观望等待', '#ffd54f'),
            'STRONG_BUY': ('强烈买入', '#00c853'),
            'STRONG_SELL': ('强烈卖出', '#d50000'),
        }
        action_text, action_color = action_map.get(action, ('观望', '#ffd54f'))

        return f"""
        <div class="section-card gauge-section">
            <div class="gauge-row">
                <div class="gauge-container">
                    <svg viewBox="0 0 200 115" class="gauge-svg">
                        <defs>
                            <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" style="stop-color:#ef5350"/>
                                <stop offset="35%" style="stop-color:#ffd54f"/>
                                <stop offset="65%" style="stop-color:#ffd54f"/>
                                <stop offset="100%" style="stop-color:#26a69a"/>
                            </linearGradient>
                        </defs>
                        <path d="M 15,100 A 85,85 0 0,1 185,100" fill="none"
                              stroke="#333" stroke-width="18" stroke-linecap="round"/>
                        <path d="M 15,100 A 85,85 0 0,1 185,100" fill="none"
                              stroke="url(#gaugeGrad)" stroke-width="18" stroke-linecap="round"/>
                        <line x1="100" y1="100" x2="100" y2="22"
                              transform="rotate({needle_deg}, 100, 100)"
                              stroke="white" stroke-width="3" stroke-linecap="round"/>
                        <circle cx="100" cy="100" r="5" fill="white"/>
                    </svg>
                    <div class="gauge-score">{'+' if clamped > 0 else ''}{clamped}</div>
                </div>
                <div class="gauge-info">
                    <div class="gauge-action" style="color:{action_color}">{action_text}</div>
                    <div class="gauge-confidence">置信度：{confidence}</div>
                    <div class="gauge-reasons">
                        {''.join(f'<div class="reason-item">• {r}</div>' for r in (getattr(signal, 'reasons', []) or [])[:4])}
                    </div>
                </div>
            </div>
        </div>"""

    def _build_price_cards(self, signal, current_price) -> str:
        """价格目标卡片"""
        buy_price = getattr(signal, 'buy_price', None)
        stop_loss = getattr(signal, 'stop_loss', None)
        take_profit = getattr(signal, 'take_profit', None)
        rr_ratio = getattr(signal, 'risk_reward_ratio', None)
        position = getattr(signal, 'suggested_position', None)

        cards = []
        if buy_price:
            cards.append(f'<div class="price-card buy"><div class="card-label">建议买入</div><div class="card-value">${buy_price:.2f}</div></div>')
        if stop_loss:
            cards.append(f'<div class="price-card stop"><div class="card-label">止损价</div><div class="card-value">${stop_loss:.2f}</div></div>')
        if take_profit:
            cards.append(f'<div class="price-card profit"><div class="card-label">止盈目标</div><div class="card-value">${take_profit:.2f}</div></div>')
        if rr_ratio:
            cards.append(f'<div class="price-card rr"><div class="card-label">风险收益比</div><div class="card-value">1:{rr_ratio:.1f}</div></div>')
        if position:
            cards.append(f'<div class="price-card pos"><div class="card-label">建议仓位</div><div class="card-value">{position:.0f}%</div></div>')

        if not cards:
            return ''

        return f'<div class="price-cards">{"".join(cards)}</div>'

    # ===== v4.2: 新增分析组件 =====

    def _build_score_table(self, signal) -> str:
        breakdown = getattr(signal, 'score_breakdown', [])
        score = getattr(signal, 'score', 0)
        if not breakdown:
            return ''

        rows = ''
        for item in breakdown:
            s = item.get('score', 0)
            if s == 0:
                continue  # Skip zero-score items to keep table clean
            score_class = 'score-pos' if s > 0 else 'score-neg'
            sign = '+' if s > 0 else ''
            indicator = item.get('indicator', '')
            value = item.get('value', '')
            ind_display = f"{indicator} ({value})" if value else indicator
            rows += f'<tr><td>{ind_display}</td><td>{item.get("signal", "")}</td><td class="{score_class}">{sign}{s}</td></tr>\n'

        # Action text
        action = getattr(signal, 'action', 'HOLD')
        action_map = {'BUY': '建议买入', 'SELL': '建议卖出', 'HOLD': '观望等待', 'STRONG_BUY': '强烈买入', 'STRONG_SELL': '强烈卖出'}
        action_text = action_map.get(action, '观望')
        sign = '+' if score > 0 else ''

        return f'''
        <div class="section-card">
            <h2>🎯 综合评分：{sign}{score} 分 → {action_text}</h2>
            <table class="score-table">
                <thead><tr><th>指标</th><th>信号</th><th>得分</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>'''

    def _build_beginner_explanations(self, indicators) -> str:
        sections = []

        # RSI
        rsi = indicators.get('rsi', 50)
        if rsi < 30:
            rsi_text = f'RSI = {rsi:.1f} → "大甩卖阶段"'
            rsi_detail = '不超买也不超卖的话说明涨势还没到头，最近从低位拉升，动能较强'
        elif rsi < 45:
            rsi_text = f'RSI = {rsi:.1f} → "偏弱，空方略占优"'
            rsi_detail = 'RSI在45以下偏弱运行'
        elif rsi < 55:
            rsi_text = f'RSI = {rsi:.1f} → "正常区间，多空平衡"'
            rsi_detail = '不超买也不超卖，观望为主'
        elif rsi < 70:
            rsi_text = f'RSI = {rsi:.1f} → "正常区间，略偏强"'
            rsi_detail = '不超买也不超卖，说明涨势还没到头'
        elif rsi < 80:
            rsi_text = f'RSI = {rsi:.1f} → "被抢购一空，小心回调"'
            rsi_detail = '超买区域，市场过于乐观'
        else:
            rsi_text = f'RSI = {rsi:.1f} → "疯狂抢购，回调风险极大"'
            rsi_detail = '极度超买，随时可能大幅回调'
        sections.append(f'<div class="explain-card"><h3>📊 RSI 相对强弱</h3><div class="explain-main">{rsi_text}</div><div class="explain-detail">{rsi_detail}</div></div>')

        # MACD
        macd = indicators.get('macd', {})
        histogram = macd.get('histogram', 0)
        interpretation = macd.get('interpretation', '')
        if histogram > 0:
            macd_text = 'MACD → "踩油门加速中"'
        else:
            macd_text = 'MACD → "松油门减速中"'
        macd_vals = f"MACD线：{macd.get('macd_line', 0):.4f}，信号线：{macd.get('signal_line', 0):.4f}，柱状图：{histogram:.4f}"
        sections.append(f'<div class="explain-card"><h3>📊 MACD 动能</h3><div class="explain-main">{macd_text}</div><div class="explain-detail">{macd_vals}<br>{interpretation}</div></div>')

        # KDJ
        kdj = indicators.get('kdj', {})
        if kdj and 'error' not in kdj:
            k, d, j = kdj.get('k', 50), kdj.get('d', 50), kdj.get('j', 50)
            if j > 100:
                kdj_text = 'KDJ → "短期涨太快了"'
                kdj_detail = f'J={j:.1f}超过100，说明短期涨得有点急，可能需要喘口气'
            elif j < 0:
                kdj_text = 'KDJ → "短期跌太多了"'
                kdj_detail = f'J={j:.1f}跌到0以下，像皮球落地要反弹'
            elif kdj.get('signal') == 'golden_cross':
                kdj_text = 'KDJ → "绿灯亮了，可以出发"'
                kdj_detail = f'K={k:.1f} D={d:.1f} J={j:.1f}，金叉买入信号'
            elif kdj.get('signal') == 'death_cross':
                kdj_text = 'KDJ → "红灯亮了，注意刹车"'
                kdj_detail = f'K={k:.1f} D={d:.1f} J={j:.1f}，死叉卖出信号'
            else:
                kdj_text = 'KDJ → "黄灯闪烁，保持观望"'
                kdj_detail = f'K={k:.1f} D={d:.1f} J={j:.1f}，{kdj.get("signal", "neutral")}'
            sections.append(f'<div class="explain-card"><h3>📊 KDJ 随机指标</h3><div class="explain-main">{kdj_text}</div><div class="explain-detail">{kdj_detail}</div></div>')

        # Volume
        vol = indicators.get('volume', {})
        if vol and 'error' not in vol:
            pattern = vol.get('pattern', '')
            vol_ratio = vol.get('volume_ratio', 1.0)
            explanation = vol.get('explanation', '')
            if '放量上涨' in pattern or (vol_ratio > 1.5 and 'bullish' in str(vol.get('signal', ''))):
                vol_text = '成交量 → "超市促销引来大批顾客"'
            elif '放量下跌' in pattern or (vol_ratio > 1.5 and 'bearish' in str(vol.get('signal', ''))):
                vol_text = '成交量 → "恐慌性抛售"'
            elif vol_ratio < 0.5:
                vol_text = '成交量 → "门可罗雀，市场观望"'
            else:
                vol_text = '成交量 → "量价平稳"'
            sections.append(f'<div class="explain-card"><h3>📊 成交量分析</h3><div class="explain-main">{vol_text}</div><div class="explain-detail">量比: {vol_ratio:.2f} | {explanation}</div></div>')

        # MA
        ma = indicators.get('ma_system', {})
        if ma:
            arr = ma.get('arrangement', '')
            if arr == '多头排列':
                ma_text = '均线 → "排队的人越排越高，趋势向上"'
            elif arr == '空头排列':
                ma_text = '均线 → "滑梯往下滑，趋势向下"'
            else:
                ma_text = '均线 → "均线缠绕，方向不明"'
            ma_vals = f"MA5={ma.get('ma5',0):.2f} MA10={ma.get('ma10',0):.2f} MA20={ma.get('ma20',0):.2f}"
            if ma.get('ma60'):
                ma_vals += f" MA60={ma['ma60']:.2f}"
            sections.append(f'<div class="explain-card"><h3>📊 均线系统</h3><div class="explain-main">{ma_text}</div><div class="explain-detail">{arr} | {ma_vals}</div></div>')

        # Bollinger
        bb = indicators.get('bbands', {})
        if isinstance(bb, dict) and 'error' not in bb:
            bw = bb.get('bandwidth', 0)
            if bw < 5:
                bb_text = '布林带 → "橡皮筋收紧，即将大动作"'
            elif bw > 20:
                bb_text = '布林带 → "橡皮筋拉得很开，波动大"'
            else:
                bb_text = '布林带 → "正常波动范围"'
            sections.append(f'<div class="explain-card"><h3>📊 布林带</h3><div class="explain-main">{bb_text}</div><div class="explain-detail">上轨=${bb.get("upper",0):.2f} 下轨=${bb.get("lower",0):.2f} 带宽={bw:.1f}%</div></div>')

        # Patterns
        if indicators.get('patterns_summary'):
            sections.append(f'<div class="explain-card"><h3>📊 形态识别</h3><div class="explain-main">{indicators["patterns_summary"]}</div></div>')

        if not sections:
            return ''
        return f'<div class="section-card"><h2>📖 技术指标解读</h2><div class="explain-grid">{"".join(sections)}</div></div>'

    def _build_key_prices_table(self, signal, sr) -> str:
        rows = []
        stop_loss = getattr(signal, 'stop_loss', None)
        if stop_loss:
            atr_pct = getattr(signal, 'atr_percent', None)
            desc = "ATR动态止损" if atr_pct else "跌破考虑止损"
            rows.append(f'<tr class="row-danger"><td>止损位</td><td>${stop_loss:.2f}</td><td>{desc}</td></tr>')

        # Supports
        supports = sr.get('supports', []) if sr else []
        for i, s in enumerate(supports[:2], 1):
            rows.append(f'<tr class="row-support"><td>支撑{i}</td><td>${s.get("price",0):.2f}</td><td>{s.get("type","")}</td></tr>')

        # Resistances
        resistances = sr.get('resistances', []) if sr else []
        for i, r in enumerate(resistances[:2], 1):
            rows.append(f'<tr class="row-resist"><td>阻力{i}</td><td>${r.get("price",0):.2f}</td><td>{r.get("type","")}</td></tr>')

        take_profit = getattr(signal, 'take_profit', None)
        if take_profit:
            rows.append(f'<tr class="row-target"><td>目标位</td><td>${take_profit:.2f}</td><td>止盈目标</td></tr>')

        if not rows:
            return ''
        return f'''
        <div class="section-card">
            <h2>🎯 关键价位</h2>
            <table class="price-table">
                <thead><tr><th>类型</th><th>价格</th><th>说明</th></tr></thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </div>'''

    def _build_action_advice(self, signal) -> str:
        action = getattr(signal, 'action', 'HOLD')
        confidence = getattr(signal, 'confidence', '中')
        buy_price = getattr(signal, 'buy_price', None)
        stop_loss = getattr(signal, 'stop_loss', None)
        take_profit = getattr(signal, 'take_profit', None)
        reasons = getattr(signal, 'reasons', [])

        if action in ('BUY', 'STRONG_BUY'):
            if confidence == '高':
                strategy = f'''<ol>
                    <li><strong>建议分批建仓</strong> — 技术面多项指标看多</li>
                    <li>买入价参考 ${buy_price:.2f}，分2-3次建仓</li>
                    <li>严格设置止损 ${stop_loss:.2f}，跌破立即离场</li>
                    <li>第一止盈目标 ${take_profit:.2f}</li>
                </ol>''' if buy_price and stop_loss and take_profit else '<p>建议逢低分批建仓，设好止损</p>'
            else:
                strategy = f'''<ol>
                    <li><strong>轻仓试探</strong> — 信号偏多但未完全确认</li>
                    <li>可在 ${buy_price:.2f} 附近小仓位试探</li>
                    <li>止损设在 ${stop_loss:.2f}</li>
                    <li>确认突破后再加仓</li>
                </ol>''' if buy_price and stop_loss else '<p>观察确认后轻仓试探</p>'
        elif action in ('SELL', 'STRONG_SELL'):
            strategy = f'''<ol>
                <li><strong>建议减仓或离场</strong> — 技术面偏空</li>
                <li>跌破 ${stop_loss:.2f} 应果断止损</li>
                <li>反弹到阻力位附近可考虑减仓</li>
            </ol>''' if stop_loss else '<p>建议减仓，设好止损保护利润</p>'
        else:
            strategy = '''<ol>
                <li><strong>暂时观望</strong> — 多空信号交织，方向不明</li>
                <li>等待明确信号再操作</li>
                <li>不要追涨杀跌，耐心等待机会</li>
            </ol>'''

        # Key reasons
        reasons_html = ''
        if reasons:
            reasons_items = ''.join(f'<li>{r}</li>' for r in reasons[:6])
            reasons_html = f'<div class="reasons-list"><h3>分析理由</h3><ol>{reasons_items}</ol></div>'

        return f'''
        <div class="section-card">
            <h2>💡 操作建议</h2>
            <div class="strategy-box">{strategy}</div>
            {reasons_html}
        </div>'''

    def _build_wisdom_section(self, signal) -> str:
        """投资智慧佐证 — 根据信号匹配相关智慧语录"""
        if not signal:
            return ''

        action = getattr(signal, 'action', 'HOLD')
        score = getattr(signal, 'score', 0)
        confidence = getattr(signal, 'confidence', '')

        # 智慧库：按场景分类，每条包含引用和出处
        wisdom_db = {
            'buy_strong': [
                ('牛市重势，熊市重质', '牛熊市智慧'),
                ('成交量是汽油，只有不断放量的股票才能走得更远', '技术分析智慧'),
                ('得双底者得天下：确定底部要看二次跌到这个价格时收什么样的K线组合', '技术分析智慧'),
            ],
            'buy_caution': [
                ('永不满仓：市场充满未知风险，不论如何看好一只股票，都要学会分批买卖', '仓位管理'),
                ('3136建仓法：金字塔式买入方法，可以有效拉低持股成本', '仓位管理'),
                ('买入前想好止盈止损：发现判断错误就必须执行交易纪律', '止损的艺术'),
            ],
            'sell': [
                ('3%左右就割肉离场：追高买入后第二天跌了，证明看错了，立即止损认错', '止损的艺术'),
                ('超出判断范围必须止损：后面的走势看不懂了', '止损的艺术'),
                ('缩量下跌是温水煮青蛙：主力资金在高位震荡时已派发筹码', '主力资金逻辑'),
            ],
            'hold': [
                ('心态第一，技术第二', '核心心法'),
                ('控制情绪，控制欲望：想要在市场里成功，这是第一个必须做到的要求', '核心心法'),
                ('每临大事有静气：能够克制住自己的脾性，任何事情都能够坦然平静地对待', '核心心法'),
            ],
            'risk': [
                ('炒股千万别融资，别加杠杆：遇到风险时，连一点抗风险的机会都没有', '风险警示'),
                ('投资是把钱扔出去，但必须能再弹回来——这根线就叫做风险控制', '风险警示'),
                ('凭借运气赚来的钱，凭实力还给了市场', '风险警示'),
                ('财不入急门：别想着一夜暴富', '人生哲学'),
            ],
            'growth': [
                ('炒股是一条修行的路：只有不断提高自己，最终才能够获得成功', '结语'),
                ('低手追求高技术，高手追求以道驭术', '技术与心态'),
                ('真正的技术派：初级看K线，中级看整体，高级看人性', '关于人性'),
            ],
        }

        # 根据信号只选 1-2 条最相关的智慧
        selected = []
        if action in ('BUY', 'STRONG_BUY'):
            if score >= 6:
                selected.append(wisdom_db['buy_strong'][0])
            selected.append(wisdom_db['buy_caution'][0])  # 永不满仓
        elif action in ('SELL', 'STRONG_SELL'):
            selected.append(wisdom_db['sell'][0])  # 止损
            if score <= -6:
                selected.append(wisdom_db['risk'][0])  # 别加杠杆
        else:
            selected.append(wisdom_db['hold'][0])  # 心态第一
            selected.append(wisdom_db['risk'][1])  # 风险控制

        quotes_html = ''
        for quote, source in selected:
            quotes_html += f'''
            <div class="wisdom-quote">
                <div class="wisdom-text">"{quote}"</div>
                <div class="wisdom-source">—— {source}</div>
            </div>'''

        return f'''
        <div class="section-card">
            <h2>📖 投资智慧</h2>
            {quotes_html}
        </div>'''

    def _build_analysis_sections(self, indicators, sr, patterns, divergence, signal, report_type) -> str:
        """文字分析区域"""
        sections = []

        # RSI
        rsi = indicators.get('rsi', 50)
        rsi_text = self._explain_rsi(rsi)
        sections.append(f'<div class="indicator-card"><h3>RSI 相对强弱 <span class="ind-val">{rsi:.1f}</span></h3><p>{rsi_text}</p></div>')

        # MACD
        macd = indicators.get('macd', {})
        macd_text = macd.get('interpretation', 'N/A')
        sections.append(f'<div class="indicator-card"><h3>MACD <span class="ind-val">{macd.get("histogram", 0):.4f}</span></h3><p>{macd_text}</p></div>')

        # 布林带
        bb = indicators.get('bbands', {})
        bb_text = self._explain_bollinger(bb, indicators.get('rsi', 50))
        if not isinstance(bb, dict) or 'error' in bb:
            bb_text = '数据不足'
        sections.append(f'<div class="indicator-card"><h3>布林带</h3><p>{bb_text}</p></div>')

        # 均线系统
        ma = indicators.get('ma_system', {})
        ma_text = f"排列: {ma.get('arrangement', 'N/A')} | MA5={ma.get('ma5', 0):.2f} MA10={ma.get('ma10', 0):.2f} MA20={ma.get('ma20', 0):.2f}"
        if ma.get('ma60'):
            ma_text += f" MA60={ma['ma60']:.2f}"
        sections.append(f'<div class="indicator-card"><h3>均线系统</h3><p>{ma_text}</p></div>')

        # KDJ
        kdj = indicators.get('kdj', {})
        if kdj and 'error' not in kdj:
            kdj_text = f"K={kdj.get('k', 0):.1f} D={kdj.get('d', 0):.1f} J={kdj.get('j', 0):.1f} | {kdj.get('signal', '')}"
            sections.append(f'<div class="indicator-card"><h3>KDJ</h3><p>{kdj_text}</p></div>')

        # 成交量
        vol = indicators.get('volume', {})
        if vol and 'error' not in vol:
            vol_text = f"{vol.get('pattern', '')} | 量比: {vol.get('volume_ratio', 0):.2f} | {vol.get('explanation', '')}"
            sections.append(f'<div class="indicator-card"><h3>成交量分析</h3><p>{vol_text}</p></div>')

        # 背离
        macd_div = divergence.get('macd', {})
        rsi_div = divergence.get('rsi', {})
        if macd_div.get('detected') or rsi_div.get('detected'):
            div_parts = []
            if macd_div.get('detected'):
                div_parts.append(f"MACD {macd_div.get('type', '')}背离")
            if rsi_div.get('detected'):
                div_parts.append(f"RSI {rsi_div.get('type', '')}背离")
            sections.append(f'<div class="indicator-card alert"><h3>⚠ 背离信号</h3><p>{"，".join(div_parts)}</p></div>')

        # 形态
        if patterns:
            candle_p = patterns.get('candlestick_patterns', [])
            chart_p = patterns.get('chart_patterns', [])
            if candle_p or chart_p:
                p_text = ''
                if candle_p:
                    names = [p.get('name', str(p)) if isinstance(p, dict) else str(p) for p in candle_p[:5]]
                    p_text += f"K线形态: {', '.join(names)}<br>"
                if chart_p:
                    names = [p.get('name', str(p)) if isinstance(p, dict) else str(p) for p in chart_p[:3]]
                    p_text += f"趋势形态: {', '.join(names)}"
                sections.append(f'<div class="indicator-card"><h3>形态识别</h3><p>{p_text}</p></div>')

        # 支撑阻力
        if sr:
            sr_parts = []
            for s in sr.get('supports', [])[:3]:
                sr_parts.append(f"支撑 ${s.get('price', 0):.2f} ({s.get('type', '')})")
            for r in sr.get('resistances', [])[:3]:
                sr_parts.append(f"阻力 ${r.get('price', 0):.2f} ({r.get('type', '')})")
            if sr_parts:
                sections.append(f'<div class="indicator-card"><h3>支撑阻力位</h3><p>{"<br>".join(sr_parts)}</p></div>')

        return f'<div class="section-card"><h2>技术指标分析</h2><div class="indicators-grid">{"".join(sections)}</div></div>'

    def _explain_rsi(self, rsi) -> str:
        if rsi < 20:
            return f"RSI={rsi:.1f}，极度超卖区，如同清仓大甩卖，反弹概率较大"
        elif rsi < 30:
            return f"RSI={rsi:.1f}，超卖区域，市场过度悲观，可能存在反弹机会"
        elif rsi < 45:
            return f"RSI={rsi:.1f}，偏弱但未超卖，空方略占优势"
        elif rsi < 55:
            return f"RSI={rsi:.1f}，中性区域，多空平衡，观望为主"
        elif rsi < 70:
            return f"RSI={rsi:.1f}，偏强运行，多方占优，趋势向好"
        elif rsi < 80:
            return f"RSI={rsi:.1f}，超买区域，市场过于乐观，注意回调风险"
        else:
            return f"RSI={rsi:.1f}，极度超买，如同疯狂抢购，回调风险极大"

    def _explain_bollinger(self, bb, rsi) -> str:
        if not isinstance(bb, dict) or 'error' in bb:
            return '数据不足'
        upper = bb.get('upper', 0)
        lower = bb.get('lower', 0)
        bandwidth = bb.get('bandwidth', 0)

        text = f"上轨=${upper:.2f} 下轨=${lower:.2f} 带宽={bandwidth:.1f}%"
        if bandwidth < 5:
            text += " | 布林带收窄，可能即将突破"
        elif bandwidth > 20:
            text += " | 布林带张开，波动较大"
        return text

    def _build_polymarket_section(self, pm_data) -> str:
        """Polymarket 情绪模块（可选）"""
        if not pm_data or not pm_data.get('available'):
            return ''

        markets = pm_data.get('relevant_markets', [])
        notes = pm_data.get('cross_reference_notes', [])

        if not markets and not notes:
            return ''

        market_cards = ''
        for m in markets[:6]:
            title = m.get('question', m.get('title', 'Unknown'))[:60]
            yes_pct = m.get('yes_probability', 0.5)
            no_pct = 1 - yes_pct
            market_cards += f"""
            <div class="pm-market">
                <div class="pm-title">{title}</div>
                <div class="pm-bar">
                    <div class="pm-yes" style="width:{yes_pct*100:.0f}%">YES {yes_pct*100:.0f}%</div>
                    <div class="pm-no" style="width:{no_pct*100:.0f}%">NO {no_pct*100:.0f}%</div>
                </div>
            </div>"""

        notes_html = ''.join(f'<div class="pm-note">• {n}</div>' for n in notes[:5])

        return f"""
        <div class="section-card pm-section">
            <h2>Polymarket 市场情绪参考</h2>
            <p class="pm-source">数据来源: Polymarket (只读，仅供参考)</p>
            <div class="pm-grid">{market_cards}</div>
            {f'<div class="pm-notes"><h3>交叉参考</h3>{notes_html}</div>' if notes_html else ''}
            <p class="pm-disclaimer">预测市场概率反映市场共识，不保证准确性</p>
        </div>"""

    def _build_disclaimer(self) -> str:
        return """
        <div class="section-card disclaimer">
            <h3>⚠ 风险提示</h3>
            <p>以上分析仅供学习参考，不构成任何投资建议。股市有风险，投资需谨慎。
            技术分析存在局限性，无法预测黑天鹅事件。请结合基本面分析和个人风险承受能力做出投资决策。</p>
        </div>"""

    def _get_css(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0f0f1a;
            color: #d1d4dc;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 20px; }

        /* Header */
        .header {
            display: flex; justify-content: space-between; align-items: flex-start;
            padding: 20px 0; border-bottom: 1px solid #2a2a3e; margin-bottom: 20px;
        }
        .header h1 { font-size: 2em; color: #fff; display: inline; margin-right: 12px; }
        .stock-name { color: #888; font-size: 1.1em; margin-right: 16px; }
        .price { font-size: 1.4em; font-weight: 600; }
        .change { font-size: 0.85em; margin-left: 8px; }
        .header-right { text-align: right; }
        .tv-button {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 8px 16px; background: #1e88e5; color: white;
            border-radius: 6px; text-decoration: none; font-size: 14px;
            transition: background 0.2s;
        }
        .tv-button:hover { background: #1565c0; }
        .timestamp { color: #666; font-size: 12px; margin-top: 8px; }

        /* Section Cards */
        .section-card {
            background: #1a1a2e; border-radius: 10px;
            padding: 20px; margin: 16px 0;
            border: 1px solid #2a2a3e;
        }
        .section-card h2 {
            color: #e0e0e0; font-size: 1.1em;
            margin-bottom: 12px; padding-bottom: 8px;
            border-bottom: 1px solid #2a2a3e;
        }

        /* Charts */
        .chart-container { width: 100%; height: 420px; }
        .chart-container-sm { width: 100%; height: 150px; }

        /* Chart header with trend badge */
        .chart-header { display: flex; justify-content: space-between; align-items: center; }
        .chart-header h2 { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }

        /* Trend badge */
        .trend-badge {
            display: inline-block; padding: 4px 12px; border-radius: 12px;
            font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
        }
        .trend-badge.bullish { background: #1b5e2033; color: #26a69a; border: 1px solid #26a69a44; }
        .trend-badge.bearish { background: #b7141433; color: #ef5350; border: 1px solid #ef535044; }
        .trend-badge.neutral { background: #33333333; color: #aaa; border: 1px solid #55555544; }

        /* Legend bar */
        .chart-legend-bar {
            display: flex; flex-wrap: wrap; gap: 12px;
            padding: 8px 4px 4px; font-size: 11px; color: #888;
        }
        .sub-legend { padding-top: 4px; }
        .legend-item { display: inline-flex; align-items: center; gap: 4px; }
        .legend-line {
            display: inline-block; width: 16px; height: 2px; border-radius: 1px;
        }
        .legend-line.legend-dashed {
            background: none !important;
            border-top: 2px dashed;
            border-color: inherit;
            height: 0;
        }
        .legend-block {
            display: inline-block; width: 12px; height: 10px; border-radius: 2px;
        }
        .legend-dot {
            display: inline-block; width: 6px; height: 6px; border-radius: 50%;
        }

        /* Gauge */
        .gauge-section { padding: 24px; }
        .gauge-row { display: flex; align-items: center; gap: 40px; }
        .gauge-container { width: 200px; text-align: center; flex-shrink: 0; }
        .gauge-svg { width: 200px; }
        .gauge-score { font-size: 2em; font-weight: 700; color: #fff; margin-top: -10px; }
        .gauge-info { flex: 1; }
        .gauge-action { font-size: 1.5em; font-weight: 700; margin-bottom: 4px; }
        .gauge-confidence { color: #888; margin-bottom: 12px; }
        .reason-item { color: #aaa; font-size: 14px; margin: 4px 0; }

        /* Price Cards */
        .price-cards {
            display: flex; gap: 12px; flex-wrap: wrap;
            margin: 16px 0;
        }
        .price-card {
            flex: 1; min-width: 140px; padding: 16px;
            border-radius: 8px; text-align: center;
        }
        .price-card .card-label { font-size: 12px; color: #aaa; margin-bottom: 4px; }
        .price-card .card-value { font-size: 1.3em; font-weight: 700; color: #fff; }
        .price-card.buy { background: #1b5e2033; border: 1px solid #26a69a44; }
        .price-card.stop { background: #b7141433; border: 1px solid #ef535044; }
        .price-card.profit { background: #0d47a133; border: 1px solid #42a5f544; }
        .price-card.rr { background: #4a148c33; border: 1px solid #ab47bc44; }
        .price-card.pos { background: #e6511133; border: 1px solid #ff704344; }

        /* Indicators Grid */
        .indicators-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 12px;
        }
        .indicator-card {
            background: #12122a; border-radius: 8px; padding: 16px;
            border: 1px solid #2a2a3e;
        }
        .indicator-card h3 { font-size: 14px; color: #ccc; margin-bottom: 8px; }
        .indicator-card p { font-size: 13px; color: #999; }
        .indicator-card.alert { border-color: #ffd54f44; background: #33290033; }
        .ind-val { float: right; color: #42a5f5; font-weight: 600; }

        /* Polymarket */
        .pm-section h2 { color: #7c4dff; }
        .pm-source { font-size: 12px; color: #666; margin-bottom: 12px; }
        .pm-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
        .pm-market { background: #12122a; border-radius: 8px; padding: 12px; border: 1px solid #2a2a3e; }
        .pm-title { font-size: 13px; color: #ccc; margin-bottom: 8px; }
        .pm-bar { display: flex; height: 24px; border-radius: 4px; overflow: hidden; font-size: 11px; }
        .pm-yes { background: #26a69a; color: white; display: flex; align-items: center; justify-content: center; }
        .pm-no { background: #ef5350; color: white; display: flex; align-items: center; justify-content: center; }
        .pm-notes { margin-top: 16px; }
        .pm-notes h3 { font-size: 14px; color: #aaa; margin-bottom: 8px; }
        .pm-note { font-size: 13px; color: #999; margin: 4px 0; }
        .pm-disclaimer { font-size: 11px; color: #555; margin-top: 12px; }

        /* Disclaimer */
        .disclaimer { border-color: #ffd54f33; }
        .disclaimer h3 { color: #ffd54f; font-size: 14px; margin-bottom: 8px; }
        .disclaimer p { font-size: 13px; color: #888; }

        /* Footer */
        .footer { text-align: center; color: #444; font-size: 12px; padding: 20px 0; }

        /* v4.2: Score table */
        .score-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
        .score-table th { text-align: left; padding: 8px 12px; border-bottom: 2px solid #2a2a3e; color: #888; font-size: 0.85em; }
        .score-table td { padding: 8px 12px; border-bottom: 1px solid #1f1f35; }
        .score-pos { color: #26a69a; font-weight: 600; }
        .score-neg { color: #ef5350; font-weight: 600; }

        /* v4.2: Beginner explanations */
        .explain-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
        .explain-card { background: #141428; border-radius: 8px; padding: 14px; border: 1px solid #2a2a3e; }
        .explain-card h3 { font-size: 0.9em; color: #aaa; margin-bottom: 8px; }
        .explain-main { font-size: 1.05em; color: #e0e0e0; font-weight: 500; margin-bottom: 6px; }
        .explain-detail { font-size: 0.85em; color: #777; }

        /* v4.2: Key prices table */
        .price-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
        .price-table th { text-align: left; padding: 8px 12px; border-bottom: 2px solid #2a2a3e; color: #888; font-size: 0.85em; }
        .price-table td { padding: 8px 12px; border-bottom: 1px solid #1f1f35; }
        .row-danger td:first-child { color: #ef5350; }
        .row-support td:first-child { color: #26a69a; }
        .row-resist td:first-child { color: #ffa726; }
        .row-target td:first-child { color: #42a5f5; }

        /* v4.2: Strategy */
        .strategy-box { background: #141428; border-radius: 8px; padding: 16px; border-left: 3px solid #42a5f5; }
        .strategy-box ol { padding-left: 20px; }
        .strategy-box li { margin: 6px 0; }
        .reasons-list { margin-top: 16px; }
        .reasons-list ol { padding-left: 20px; color: #aaa; }
        .reasons-list li { margin: 4px 0; font-size: 0.9em; }
        /* Wisdom section */
        .wisdom-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
        .wisdom-quote { background: #141428; border-radius: 8px; padding: 16px; border-left: 3px solid #ffd54f; }
        .wisdom-text { color: #e0e0e0; font-style: italic; line-height: 1.6; }
        .wisdom-source { color: #888; font-size: 0.85em; margin-top: 8px; text-align: right; }

        /* v4.2: Toggle toolbar */
        .chart-toggles { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #2a2a3e; }
        .toggle-btn {
            padding: 5px 14px; border-radius: 16px; border: 1px solid #444;
            background: transparent; color: #888; font-size: 12px; cursor: pointer;
            transition: all 0.2s;
        }
        .toggle-btn:hover { border-color: #666; color: #bbb; }
        .toggle-btn.active { background: #1e88e5; border-color: #1e88e5; color: white; }

        /* Responsive */
        @media (max-width: 768px) {
            .gauge-row { flex-direction: column; }
            .price-cards { flex-direction: column; }
            .indicators-grid { grid-template-columns: 1fr; }
            .explain-grid { grid-template-columns: 1fr; }
        }
        """
