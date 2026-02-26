"""
小白友好股票分析模块 v3.4

功能：
- 用通俗易懂的语言解释技术指标
- 综合分析给出买卖点建议
- 支持简洁版和详细版报告
- 港股本地计算支持
- ATR 动态止损
- 成交量/均线分析
- 仓位建议

v3.4 新增:
- K线形态识别小白解读（锤子线、吞没、十字星、早晨之星等）
- 趋势形态识别小白解读（双底、双顶、头肩顶/底、三角形）
- 形态信号纳入评分系统

v3.3:
- KDJ 随机指标小白解读
- 背离信号解读
- 支撑阻力位解读
- OBV 量能解读
- 威廉指标/乖离率解读
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class TradingSignal:
    """交易信号"""
    action: str  # BUY, SELL, HOLD
    confidence: str  # 高, 中, 低
    buy_price: Optional[float] = None  # 建议买入价
    sell_price: Optional[float] = None  # 建议卖出价
    stop_loss: Optional[float] = None  # 止损价
    take_profit: Optional[float] = None  # 止盈价
    reasons: List[str] = field(default_factory=list)  # 理由列表
    # v3.2 字段
    atr: Optional[float] = None  # ATR 值
    atr_percent: Optional[float] = None  # ATR 百分比
    risk_reward_ratio: Optional[float] = None  # 风险收益比
    suggested_position: Optional[float] = None  # 建议仓位百分比
    volume_signal: Optional[str] = None  # 成交量信号
    ma_trend: Optional[str] = None  # 均线趋势
    # v3.3 新增字段
    kdj_signal: Optional[str] = None  # KDJ 信号
    divergence_signal: Optional[str] = None  # 背离信号
    obv_signal: Optional[str] = None  # OBV 信号
    support_price: Optional[float] = None  # 最近支撑位
    resistance_price: Optional[float] = None  # 最近阻力位
    score: Optional[int] = None  # 综合评分
    # v3.4 形态识别
    patterns_signal: Optional[str] = None  # 形态综合信号
    patterns_count: Optional[int] = None  # 识别到的形态数量
    # v4.2 评分明细
    score_breakdown: List[Dict] = field(default_factory=list)  # [{'indicator','value','signal','score'}]


def explain_rsi_simple(rsi: float) -> str:
    """用小白语言解释 RSI"""
    if rsi < 30:
        return f"🟢 **超卖** ({rsi:.1f}) - 股票被卖得太多了，就像商场大甩卖，价格可能已经跌过头，是潜在的捡便宜机会"
    elif rsi < 40:
        return f"🟡 **偏弱** ({rsi:.1f}) - 股票有点疲软，买家不太积极，但还没到跌过头的程度"
    elif rsi < 60:
        return f"⚪ **中性** ({rsi:.1f}) - 买卖力量均衡，股票在正常波动，没有明显的超买或超卖"
    elif rsi < 70:
        return f"🟡 **偏强** ({rsi:.1f}) - 买家比较积极，股票走势还不错，但要注意别追高"
    else:
        return f"🔴 **超买** ({rsi:.1f}) - 股票被买得太多了，就像热门商品被抢购一空，价格可能涨过头，要小心回调"


def explain_macd_simple(macd_line: float, signal_line: float, histogram: float, prev_histogram: float = None) -> str:
    """用小白语言解释 MACD"""
    # 判断趋势和交叉
    if prev_histogram is not None:
        if histogram > 0 and prev_histogram <= 0:
            return f"🟢 **金叉出现** - 短期上涨动能超过了长期动能，就像汽车踩了油门开始加速，是买入信号"
        elif histogram < 0 and prev_histogram >= 0:
            return f"🔴 **死叉出现** - 短期动能开始减弱，就像汽车松了油门开始减速，是卖出警告"

    if histogram > 0:
        strength = "强劲" if histogram > 1 else "温和"
        return f"🟢 **多头趋势** - 上涨动能{strength}，就像顺风骑车，省力又快"
    else:
        strength = "明显" if histogram < -1 else "轻微"
        return f"🔴 **空头趋势** - 下跌动能{strength}，就像逆风骑车，需要更多力气"


def explain_bollinger_simple(price: float, upper: float, middle: float, lower: float) -> str:
    """用小白语言解释布林带"""
    band_width = upper - lower
    position = (price - lower) / band_width * 100 if band_width > 0 else 50

    if price < lower:
        return f"🟢 **跌破下轨** - 股价已经跌到了'地板'下面 (${lower:.2f})，就像橡皮筋拉得太长，可能要弹回来了"
    elif price < lower + band_width * 0.2:
        return f"🟢 **接近下轨** - 股价在'地板'附近 (${lower:.2f})，处于相对低位，可能是买入机会"
    elif price > upper:
        return f"🔴 **突破上轨** - 股价已经涨到了'天花板'上面 (${upper:.2f})，涨得有点猛，可能要回落"
    elif price > upper - band_width * 0.2:
        return f"🟡 **接近上轨** - 股价在'天花板'附近 (${upper:.2f})，处于相对高位，要注意回调风险"
    else:
        return f"⚪ **正常区间** - 股价在中间位置 (中轨 ${middle:.2f})，波动正常"


def explain_volume_simple(volume_ratio: float, pattern: str) -> str:
    """用小白语言解释成交量"""
    if pattern == "放量上涨":
        return f"📈 **放量上涨** (量比 {volume_ratio:.1f}) - 买盘积极涌入，像超市促销引来大批顾客，上涨动力充足"
    elif pattern == "放量下跌":
        return f"📉 **放量下跌** (量比 {volume_ratio:.1f}) - 卖盘大量涌出，像恐慌性抛售，需要警惕"
    elif pattern == "缩量上涨":
        return f"📈 **缩量上涨** (量比 {volume_ratio:.1f}) - 涨是涨了但买家不多，像没人气的促销，后劲可能不足"
    elif pattern == "缩量下跌":
        return f"📉 **缩量下跌** (量比 {volume_ratio:.1f}) - 跌但卖家也不多了，像甩卖接近尾声，可能快到底了"
    elif pattern == "放量震荡":
        return f"⚡ **放量震荡** (量比 {volume_ratio:.1f}) - 交易活跃但方向不明，多空在激烈博弈"
    else:
        return f"➡️ **量价平稳** (量比 {volume_ratio:.1f}) - 一切正常，没有异常信号"


def explain_ma_simple(arrangement: str, price_above: List[str], price_below: List[str]) -> str:
    """用小白语言解释均线"""
    if arrangement == "多头排列":
        return f"🟢 **多头排列** - 短期均线在上，长期均线在下，像排队的人越排越高，趋势向上"
    elif arrangement == "空头排列":
        return f"🔴 **空头排列** - 短期均线在下，长期均线在上，像滑梯往下滑，趋势向下"
    else:
        above_str = '/'.join(price_above) if price_above else "无"
        below_str = '/'.join(price_below) if price_below else "无"
        return f"🟡 **均线缠绕** - 均线交织在一起，方向不明朗（价格在 {above_str} 上方，在 {below_str} 下方）"


def explain_atr_simple(atr_percent: float) -> str:
    """用小白语言解释 ATR（波动性）"""
    if atr_percent > 5:
        return f"⚠️ **高波动** ({atr_percent:.1f}%) - 股价波动剧烈，像坐过山车，风险较大但机会也大"
    elif atr_percent > 3:
        return f"🔔 **中等波动** ({atr_percent:.1f}%) - 股价有一定波动，正常范围"
    else:
        return f"😌 **低波动** ({atr_percent:.1f}%) - 股价比较稳定，适合稳健型投资"


# ============================================
# v3.3 新增小白解读函数
# ============================================

def explain_kdj_simple(k: float, d: float, j: float, signal: str) -> str:
    """用小白语言解释 KDJ 随机指标"""
    if signal == 'golden_cross':
        return f"🟢 **KDJ 金叉** (K={k:.0f}, D={d:.0f}, J={j:.0f}) - 短期买入信号，像绿灯亮了可以出发"
    elif signal == 'death_cross':
        return f"🔴 **KDJ 死叉** (K={k:.0f}, D={d:.0f}, J={j:.0f}) - 短期卖出信号，像红灯亮了要刹车"
    elif signal == 'overbought' or signal == 'high_zone':
        return f"🔴 **KDJ 超买** (K={k:.0f}, D={d:.0f}, J={j:.0f}) - 短期涨太快了，像弹簧压得太紧可能要回弹"
    elif signal == 'oversold' or signal == 'low_zone':
        return f"🟢 **KDJ 超卖** (K={k:.0f}, D={d:.0f}, J={j:.0f}) - 短期跌太多了，像皮球落地可能要反弹"
    else:
        return f"⚪ **KDJ 中性** (K={k:.0f}, D={d:.0f}, J={j:.0f}) - 目前没有明显的超买超卖信号"


def explain_divergence_simple(divergence_type: str, indicator_name: str = "MACD") -> str:
    """用小白语言解释背离信号"""
    if divergence_type == 'bullish':
        return f"🟢 **{indicator_name} 底背离** - 价格在创新低，但{indicator_name}没有创新低，说明下跌动能在减弱，像马拉松跑到后面速度慢下来了，可能要反弹"
    elif divergence_type == 'bearish':
        return f"🔴 **{indicator_name} 顶背离** - 价格在创新高，但{indicator_name}没有创新高，说明上涨动能在减弱，像爬山快到顶了越来越吃力，小心回调"
    else:
        return f"⚪ **无{indicator_name}背离** - 价格和指标走势一致，趋势正常"


def explain_support_resistance_simple(
    current_price: float,
    nearest_support: dict,
    nearest_resistance: dict
) -> str:
    """用小白语言解释支撑阻力位"""
    parts = []

    if nearest_support:
        support_price = nearest_support['price']
        distance_pct = (current_price - support_price) / current_price * 100
        parts.append(f"📉 **最近支撑位**: ${support_price:.2f} (距离 {distance_pct:.1f}%) - 跌到这里可能会有买盘接住，像地板一样")

    if nearest_resistance:
        resist_price = nearest_resistance['price']
        distance_pct = (resist_price - current_price) / current_price * 100
        parts.append(f"📈 **最近阻力位**: ${resist_price:.2f} (距离 {distance_pct:.1f}%) - 涨到这里可能会有卖盘压制，像天花板一样")

    if not parts:
        return "暂无明确的支撑阻力位"

    return "\n".join(parts)


def explain_obv_simple(signal: str, obv_trend: str, price_trend: str) -> str:
    """用小白语言解释 OBV 能量潮"""
    if signal == 'confirmed_up':
        return "🟢 **OBV 确认上涨** - 价格涨，资金也在流入，像涨潮一样水涨船高，趋势健康"
    elif signal == 'confirmed_down':
        return "🔴 **OBV 确认下跌** - 价格跌，资金也在流出，像退潮一样水落船低，趋势延续"
    elif signal == 'bullish_divergence':
        return "🟢 **OBV 底背离** - 价格在跌，但资金在悄悄流入，像有人在偷偷抄底，关注反弹机会"
    elif signal == 'bearish_divergence':
        return "🔴 **OBV 顶背离** - 价格在涨，但资金在悄悄流出，像有人在偷偷出货，警惕回调风险"
    else:
        return "⚪ **OBV 中性** - 量价关系正常"


def explain_williams_simple(wr: float, signal: str) -> str:
    """用小白语言解释威廉指标"""
    if signal == 'overbought':
        return f"🔴 **威廉指标超买** ({wr:.0f}) - 短期涨得太急，像冲刺跑太快要喘气，可能要回调"
    elif signal == 'oversold':
        return f"🟢 **威廉指标超卖** ({wr:.0f}) - 短期跌得太急，像跌倒了要爬起来，可能要反弹"
    else:
        return f"⚪ **威廉指标中性** ({wr:.0f}) - 目前处于正常区间"


def explain_bias_simple(bias6: float, signal: str) -> str:
    """用小白语言解释乖离率"""
    if signal == 'overbought':
        return f"🔴 **乖离率偏高** ({bias6:.1f}%) - 股价跑得比均线快太多了，像跑步冲太快会累，可能要回来休息（回调）"
    elif signal == 'oversold':
        return f"🟢 **乖离率偏低** ({bias6:.1f}%) - 股价跌得比均线远太多了，像橡皮筋拉太长会弹回来，可能要反弹"
    else:
        return f"⚪ **乖离率正常** ({bias6:.1f}%) - 股价和均线走得差不多齐，比较健康"


# ============================================
# v3.4 形态识别小白解读
# ============================================

# K线形态中英文映射
CANDLESTICK_NAMES = {
    'doji': '十字星',
    'hammer': '锤子线',
    'hanging_man': '上吊线',
    'bullish_engulfing': '看涨吞没',
    'bearish_engulfing': '看跌吞没',
    'morning_star': '早晨之星',
    'evening_star': '黄昏之星',
    'three_white_soldiers': '三只白兵',
    'three_black_crows': '三只乌鸦',
    'shooting_star': '射击之星',
    'inverted_hammer': '倒锤子'
}

# 趋势形态中英文映射
CHART_PATTERN_NAMES = {
    'double_bottom': '双底',
    'double_top': '双顶',
    'head_and_shoulders_top': '头肩顶',
    'head_and_shoulders_bottom': '头肩底',
    'ascending_triangle': '上升三角形',
    'descending_triangle': '下降三角形',
    'symmetric_triangle': '对称三角形'
}


def explain_candlestick_pattern_simple(pattern: dict) -> str:
    """用小白语言解释K线形态"""
    pattern_type = pattern.get('pattern', '')
    signal = pattern.get('signal', 'neutral')
    strength = pattern.get('strength', 'medium')

    cn_name = CANDLESTICK_NAMES.get(pattern_type, pattern_type)

    # 强度描述
    strength_desc = {
        'very_strong': '非常强烈',
        'strong': '强烈',
        'medium': '中等',
        'weak': '较弱'
    }.get(strength, '中等')

    # 各形态的小白解读
    explanations = {
        'doji': "⚪ **十字星** - 多空双方势均力敌，就像拔河比赛打成平手。当前趋势可能要变化，要密切观察",
        'hammer': "🟢 **锤子线** (看涨) - 像一把锤子倒立，下影线很长说明下方有人接盘。出现在下跌后，是见底信号",
        'hanging_man': "🔴 **上吊线** (看跌) - 形状像锤子但出现在上涨后，说明上方卖压开始出现。可能是见顶信号",
        'bullish_engulfing': "🟢 **看涨吞没** (强信号) - 大阳线完全包住前一根阴线，像大鱼吃小鱼。买方力量占优，反转信号",
        'bearish_engulfing': "🔴 **看跌吞没** (强信号) - 大阴线完全包住前一根阳线，卖方力量压倒买方。下跌信号",
        'morning_star': "🟢 **早晨之星** (强信号) - 三根K线组成，像黎明前的启明星。典型的底部反转形态，买入机会",
        'evening_star': "🔴 **黄昏之星** (强信号) - 三根K线组成，像日落前的昏星。典型的顶部反转形态，卖出信号",
        'three_white_soldiers': "🟢 **三只白兵** (非常强) - 连续三根阳线稳步上涨，像士兵列队前进。强烈的上涨信号",
        'three_black_crows': "🔴 **三只乌鸦** (非常强) - 连续三根阴线稳步下跌，像乌鸦报丧。强烈的下跌信号",
        'shooting_star': "🔴 **射击之星** - 上影线很长，像流星划过。出现在上涨后说明上方抛压重，可能见顶",
        'inverted_hammer': "🟢 **倒锤子** - 出现在下跌后的长上影线，买方尝试反攻。如果次日确认，是反转信号"
    }

    explanation = explanations.get(pattern_type, f"识别到 {cn_name} 形态")
    return f"{explanation}\n  ⭐ 信号强度: {strength_desc}"


def explain_chart_pattern_simple(pattern: dict) -> str:
    """用小白语言解释趋势形态"""
    pattern_type = pattern.get('pattern', '')
    signal = pattern.get('signal', 'neutral')
    strength = pattern.get('strength', 'medium')

    cn_name = CHART_PATTERN_NAMES.get(pattern_type, pattern_type)

    # 强度描述
    strength_desc = {
        'very_strong': '非常可靠',
        'strong': '比较可靠',
        'medium': '参考意义',
        'weak': '需要验证'
    }.get(strength, '参考意义')

    # 各形态的小白解读
    explanations = {
        'double_bottom': "🟢 **双底形态** (W底) - 股价两次探底后反弹，像字母W。经典的底部反转形态，突破颈线后看涨",
        'double_top': "🔴 **双顶形态** (M头) - 股价两次冲高后回落，像字母M。经典的顶部形态，跌破颈线后看跌",
        'head_and_shoulders_top': "🔴 **头肩顶** - 中间高两边低，像人的头和肩膀。是最可靠的顶部反转形态之一",
        'head_and_shoulders_bottom': "🟢 **头肩底** - 中间低两边高，倒过来的头肩形态。是可靠的底部反转信号",
        'ascending_triangle': "🟢 **上升三角形** - 底部逐步抬高，顶部水平。说明买方逐渐占优，通常向上突破",
        'descending_triangle': "🔴 **下降三角形** - 顶部逐步降低，底部水平。说明卖方逐渐占优，通常向下突破",
        'symmetric_triangle': "⚪ **对称三角形** - 高点降低、低点抬高，形成收敛。突破方向不确定，等待突破后跟进"
    }

    explanation = explanations.get(pattern_type, f"识别到 {cn_name} 形态")
    return f"{explanation}\n  ⭐ 可靠度: {strength_desc}"


def explain_patterns_simple(patterns_data: dict) -> str:
    """综合解释所有识别到的形态"""
    if not patterns_data:
        return "⚪ 暂未识别到明显形态"

    all_patterns = patterns_data.get('all_patterns', [])
    if not all_patterns:
        return "⚪ 暂未识别到明显形态"

    result_lines = ["📊 **形态识别结果**"]

    # K线形态
    candlestick = patterns_data.get('candlestick_patterns', [])
    if candlestick:
        result_lines.append("\n**K线形态:**")
        for p in candlestick[:3]:  # 最多显示3个
            result_lines.append(f"  • {explain_candlestick_pattern_simple(p)}")

    # 趋势形态
    chart = patterns_data.get('chart_patterns', [])
    if chart:
        result_lines.append("\n**趋势形态:**")
        for p in chart[:2]:  # 最多显示2个
            result_lines.append(f"  • {explain_chart_pattern_simple(p)}")

    # 综合判断
    signal = patterns_data.get('signal', 'neutral')
    bullish = patterns_data.get('bullish_count', 0)
    bearish = patterns_data.get('bearish_count', 0)

    result_lines.append(f"\n**形态综合判断:**")
    if signal == 'bullish':
        result_lines.append(f"  🟢 看涨形态占优 (看涨{bullish}个 vs 看跌{bearish}个)")
    elif signal == 'bearish':
        result_lines.append(f"  🔴 看跌形态占优 (看跌{bearish}个 vs 看涨{bullish}个)")
    else:
        result_lines.append(f"  ⚪ 形态信号中性 (看涨{bullish}个 vs 看跌{bearish}个)")

    return "\n".join(result_lines)


def explain_trend_simple(prices: List[float], period_name: str = "近期") -> str:
    """用小白语言解释趋势"""
    if len(prices) < 5:
        return "数据不足，无法判断趋势"

    start_price = prices[0]
    end_price = prices[-1]
    change_pct = (end_price - start_price) / start_price * 100

    # 计算波动性
    max_price = max(prices)
    min_price = min(prices)
    volatility = (max_price - min_price) / start_price * 100

    if change_pct > 10:
        trend = f"📈 **强势上涨** - {period_name}涨了 {change_pct:.1f}%，像坐电梯往上，势头很猛"
    elif change_pct > 3:
        trend = f"📈 **温和上涨** - {period_name}涨了 {change_pct:.1f}%，像爬楼梯，稳步向上"
    elif change_pct > -3:
        trend = f"➡️ **横盘震荡** - {period_name}基本持平 ({change_pct:+.1f}%)，在一个区间内来回波动"
    elif change_pct > -10:
        trend = f"📉 **温和下跌** - {period_name}跌了 {abs(change_pct):.1f}%，像下楼梯，逐步下行"
    else:
        trend = f"📉 **大幅下跌** - {period_name}跌了 {abs(change_pct):.1f}%，跌势比较急"

    # 添加波动性说明
    if volatility > 20:
        trend += f"\n  ⚠️ 波动较大 ({volatility:.1f}%)，坐过山车的感觉，风险较高"
    elif volatility > 10:
        trend += f"\n  🔔 波动中等 ({volatility:.1f}%)，有起有伏但还算正常"

    return trend


def calculate_support_resistance(prices: List[float], current_price: float) -> Dict[str, float]:
    """计算支撑位和阻力位"""
    if len(prices) < 20:
        return {}

    # 简单方法：使用近期高低点
    recent_high = max(prices[-20:])
    recent_low = min(prices[-20:])

    # 计算关键位置
    result = {
        'strong_resistance': recent_high,  # 强阻力位 = 近期最高
        'weak_resistance': current_price + (recent_high - current_price) * 0.382,  # 斐波那契
        'weak_support': current_price - (current_price - recent_low) * 0.382,
        'strong_support': recent_low,  # 强支撑位 = 近期最低
    }

    return result


def generate_trading_recommendation(
    ticker: str,
    current_price: float,
    rsi: float,
    macd_histogram: float,
    prev_macd_histogram: float,
    bb_upper: float,
    bb_middle: float,
    bb_lower: float,
    prices_1m: List[float] = None,
    prices_3m: List[float] = None,
    # v3.2 参数
    atr: float = None,
    atr_percent: float = None,
    volume_ratio: float = None,
    volume_signal: str = None,
    ma_trend: str = None,
    ma_arrangement: str = None,
    # v3.3 新增参数
    kdj_k: float = None,
    kdj_d: float = None,
    kdj_j: float = None,
    kdj_signal: str = None,
    macd_divergence: str = None,
    rsi_divergence: str = None,
    obv_signal: str = None,
    williams_signal: str = None,
    bias_signal: str = None,
    nearest_support: float = None,
    nearest_resistance: float = None,
    # v3.4 形态识别参数
    patterns_signal: str = None,  # 'bullish', 'bearish', 'neutral'
    patterns_data: dict = None  # 完整形态数据
) -> TradingSignal:
    """
    综合分析生成交易建议 (v3.4)

    综合策略：
    1. RSI 超卖/超买
    2. MACD 金叉/死叉
    3. 布林带位置
    4. 趋势判断
    5. 成交量配合
    6. 均线排列
    7. ATR 动态止损
    8. [v3.3] KDJ 随机指标
    9. [v3.3] MACD/RSI 背离
    10. [v3.3] OBV 量能
    11. [v3.3] 威廉指标/乖离率
    12. [v3.3] 支撑阻力位
    13. [v3.4] K线形态 + 趋势形态
    """
    reasons = []
    breakdown = []  # v4.2 评分明细
    buy_score = 0  # 正数倾向买入，负数倾向卖出

    # === RSI 分析 ===
    if rsi < 30:
        buy_score += 3
        reasons.append("✅ RSI 超卖 (<30)，股价可能跌过头")
        breakdown.append({'indicator': 'RSI', 'value': f'{rsi:.1f}', 'signal': '超卖', 'score': 3})
    elif rsi < 40:
        buy_score += 1
        reasons.append("📍 RSI 偏低，股价相对便宜")
        breakdown.append({'indicator': 'RSI', 'value': f'{rsi:.1f}', 'signal': '偏低', 'score': 1})
    elif rsi > 70:
        buy_score -= 3
        reasons.append("⚠️ RSI 超买 (>70)，股价可能涨过头")
        breakdown.append({'indicator': 'RSI', 'value': f'{rsi:.1f}', 'signal': '超买', 'score': -3})
    elif rsi > 60:
        buy_score -= 1
        reasons.append("📍 RSI 偏高，追高需谨慎")
        breakdown.append({'indicator': 'RSI', 'value': f'{rsi:.1f}', 'signal': '偏高', 'score': -1})
    else:
        breakdown.append({'indicator': 'RSI', 'value': f'{rsi:.1f}', 'signal': '中性', 'score': 0})

    # === MACD 分析 ===
    if macd_histogram > 0 and prev_macd_histogram <= 0:
        buy_score += 3
        reasons.append("✅ MACD 金叉，上涨动能启动")
        breakdown.append({'indicator': 'MACD', 'value': f'{macd_histogram:.4f}', 'signal': '金叉', 'score': 3})
    elif macd_histogram < 0 and prev_macd_histogram >= 0:
        buy_score -= 3
        reasons.append("⚠️ MACD 死叉，下跌动能启动")
        breakdown.append({'indicator': 'MACD', 'value': f'{macd_histogram:.4f}', 'signal': '死叉', 'score': -3})
    elif macd_histogram > 0:
        buy_score += 1
        reasons.append("📍 MACD 多头趋势")
        breakdown.append({'indicator': 'MACD', 'value': f'{macd_histogram:.4f}', 'signal': '多头趋势', 'score': 1})
    else:
        buy_score -= 1
        reasons.append("📍 MACD 空头趋势")
        breakdown.append({'indicator': 'MACD', 'value': f'{macd_histogram:.4f}', 'signal': '空头趋势', 'score': -1})

    # === 布林带分析 ===
    if current_price < bb_lower:
        buy_score += 2
        reasons.append("✅ 跌破布林带下轨，可能超跌反弹")
        breakdown.append({'indicator': '布林带', 'value': f'{current_price:.2f}', 'signal': '跌破下轨', 'score': 2})
    elif current_price < bb_lower + (bb_middle - bb_lower) * 0.3:
        buy_score += 1
        reasons.append("📍 接近布林带下轨，相对低位")
        breakdown.append({'indicator': '布林带', 'value': f'{current_price:.2f}', 'signal': '接近下轨', 'score': 1})
    elif current_price > bb_upper:
        buy_score -= 2
        reasons.append("⚠️ 突破布林带上轨，可能回调")
        breakdown.append({'indicator': '布林带', 'value': f'{current_price:.2f}', 'signal': '突破上轨', 'score': -2})
    elif current_price > bb_upper - (bb_upper - bb_middle) * 0.3:
        buy_score -= 1
        reasons.append("📍 接近布林带上轨，追高风险")
        breakdown.append({'indicator': '布林带', 'value': f'{current_price:.2f}', 'signal': '接近上轨', 'score': -1})
    else:
        breakdown.append({'indicator': '布林带', 'value': f'{current_price:.2f}', 'signal': '正常区间', 'score': 0})

    # === KDJ 分析 (v3.3 新增) ===
    if kdj_signal:
        if kdj_signal == 'golden_cross':
            buy_score += 3
            reasons.append("✅ KDJ 金叉，短期买入信号")
            breakdown.append({'indicator': 'KDJ', 'value': f'{kdj_k:.1f}', 'signal': '金叉', 'score': 3})
        elif kdj_signal == 'death_cross':
            buy_score -= 3
            reasons.append("⚠️ KDJ 死叉，短期卖出信号")
            breakdown.append({'indicator': 'KDJ', 'value': f'{kdj_k:.1f}', 'signal': '死叉', 'score': -3})
        elif kdj_signal in ['oversold', 'low_zone']:
            buy_score += 2
            reasons.append("✅ KDJ 超卖，短期可能反弹")
            breakdown.append({'indicator': 'KDJ', 'value': f'{kdj_k:.1f}', 'signal': '超卖', 'score': 2})
        elif kdj_signal in ['overbought', 'high_zone']:
            buy_score -= 2
            reasons.append("⚠️ KDJ 超买，短期可能回调")
            breakdown.append({'indicator': 'KDJ', 'value': f'{kdj_k:.1f}', 'signal': '超买', 'score': -2})

    # === 背离分析 (v3.3 新增) - 背离是强信号 ===
    if macd_divergence == 'bullish':
        buy_score += 4
        reasons.append("🔥 MACD 底背离，强烈反弹信号")
        breakdown.append({'indicator': 'MACD背离', 'value': '', 'signal': '底背离', 'score': 4})
    elif macd_divergence == 'bearish':
        buy_score -= 4
        reasons.append("🔥 MACD 顶背离，强烈回调信号")
        breakdown.append({'indicator': 'MACD背离', 'value': '', 'signal': '顶背离', 'score': -4})

    if rsi_divergence == 'bullish':
        buy_score += 3
        reasons.append("✅ RSI 底背离，动能转强")
        breakdown.append({'indicator': 'RSI背离', 'value': '', 'signal': '底背离', 'score': 3})
    elif rsi_divergence == 'bearish':
        buy_score -= 3
        reasons.append("⚠️ RSI 顶背离，动能转弱")
        breakdown.append({'indicator': 'RSI背离', 'value': '', 'signal': '顶背离', 'score': -3})

    # === OBV 分析 (v3.3 新增) ===
    if obv_signal:
        if obv_signal == 'bullish_divergence':
            buy_score += 2
            reasons.append("📊 OBV 底背离，资金悄悄流入")
            breakdown.append({'indicator': 'OBV', 'value': '', 'signal': '底背离', 'score': 2})
        elif obv_signal == 'bearish_divergence':
            buy_score -= 2
            reasons.append("📊 OBV 顶背离，资金悄悄流出")
            breakdown.append({'indicator': 'OBV', 'value': '', 'signal': '顶背离', 'score': -2})
        elif obv_signal == 'confirmed_up':
            buy_score += 1
            reasons.append("📊 OBV 确认上涨趋势")
            breakdown.append({'indicator': 'OBV', 'value': '', 'signal': '确认上涨', 'score': 1})
        elif obv_signal == 'confirmed_down':
            buy_score -= 1
            reasons.append("📊 OBV 确认下跌趋势")
            breakdown.append({'indicator': 'OBV', 'value': '', 'signal': '确认下跌', 'score': -1})

    # === 威廉指标/乖离率 (v3.3 新增) ===
    if williams_signal == 'oversold':
        buy_score += 1
        reasons.append("📍 威廉指标超卖")
        breakdown.append({'indicator': '威廉指标', 'value': '', 'signal': '超卖', 'score': 1})
    elif williams_signal == 'overbought':
        buy_score -= 1
        reasons.append("📍 威廉指标超买")
        breakdown.append({'indicator': '威廉指标', 'value': '', 'signal': '超买', 'score': -1})

    if bias_signal == 'oversold':
        buy_score += 1
        reasons.append("📍 乖离率偏低，可能反弹")
        breakdown.append({'indicator': '乖离率', 'value': '', 'signal': '偏低', 'score': 1})
    elif bias_signal == 'overbought':
        buy_score -= 1
        reasons.append("📍 乖离率偏高，可能回调")
        breakdown.append({'indicator': '乖离率', 'value': '', 'signal': '偏高', 'score': -1})

    # === 成交量分析 ===
    if volume_signal:
        if volume_signal == "bullish" and volume_ratio and volume_ratio > 1.5:
            buy_score += 2
            reasons.append(f"📊 放量上涨 (量比 {volume_ratio:.1f})，买盘积极")
            breakdown.append({'indicator': '成交量', 'value': f'{volume_ratio:.1f}', 'signal': '放量上涨', 'score': 2})
        elif volume_signal == "bearish" and volume_ratio and volume_ratio > 1.5:
            buy_score -= 2
            reasons.append(f"📊 放量下跌 (量比 {volume_ratio:.1f})，卖压较大")
            breakdown.append({'indicator': '成交量', 'value': f'{volume_ratio:.1f}', 'signal': '放量下跌', 'score': -2})
        elif volume_signal == "neutral" and volume_ratio and volume_ratio < 0.7:
            if macd_histogram < 0:
                buy_score += 1
                reasons.append(f"📊 缩量下跌 (量比 {volume_ratio:.1f})，卖压减轻")
                breakdown.append({'indicator': '成交量', 'value': f'{volume_ratio:.1f}', 'signal': '缩量下跌', 'score': 1})

    # === 均线分析 ===
    if ma_arrangement:
        if ma_arrangement == "多头排列":
            buy_score += 2
            reasons.append("📈 均线多头排列，趋势向上")
            breakdown.append({'indicator': '均线', 'value': '', 'signal': '多头排列', 'score': 2})
        elif ma_arrangement == "空头排列":
            buy_score -= 2
            reasons.append("📉 均线空头排列，趋势向下")
            breakdown.append({'indicator': '均线', 'value': '', 'signal': '空头排列', 'score': -2})

    # === 趋势分析 ===
    if prices_1m and len(prices_1m) >= 5:
        change_1m = (prices_1m[-1] - prices_1m[0]) / prices_1m[0] * 100
        if change_1m < -15:
            buy_score += 1
            reasons.append(f"📍 近1月跌幅较大 ({change_1m:.1f}%)，可能超跌")
            breakdown.append({'indicator': '趋势', 'value': f'{change_1m:.1f}%', 'signal': '近期跌幅大', 'score': 1})
        elif change_1m > 15:
            buy_score -= 1
            reasons.append(f"📍 近1月涨幅较大 ({change_1m:.1f}%)，注意追高")
            breakdown.append({'indicator': '趋势', 'value': f'{change_1m:.1f}%', 'signal': '近期涨幅大', 'score': -1})

    # === 支撑阻力位分析 (v3.3 新增) ===
    if nearest_support and nearest_resistance:
        support_distance = (current_price - nearest_support) / current_price * 100
        resist_distance = (nearest_resistance - current_price) / current_price * 100

        if support_distance < 3:  # 接近支撑位
            buy_score += 1
            reasons.append(f"📍 接近支撑位 ${nearest_support:.2f}，可能有支撑")
            breakdown.append({'indicator': '支撑阻力', 'value': f'${nearest_support:.2f}', 'signal': '接近支撑', 'score': 1})
        if resist_distance < 3:  # 接近阻力位
            buy_score -= 1
            reasons.append(f"📍 接近阻力位 ${nearest_resistance:.2f}，可能有压力")
            breakdown.append({'indicator': '支撑阻力', 'value': f'${nearest_resistance:.2f}', 'signal': '接近阻力', 'score': -1})

    # === 形态识别分析 (v3.4 新增) ===
    if patterns_data:
        all_patterns = patterns_data.get('all_patterns', [])

        # 按形态强度和类型评分
        for pattern in all_patterns:
            p_signal = pattern.get('signal', 'neutral')
            p_strength = pattern.get('strength', 'medium')
            p_name = pattern.get('pattern', '')

            # 强信号形态（三只白兵/乌鸦、早晨/黄昏之星、头肩、双底双顶）
            strong_patterns = ['three_white_soldiers', 'three_black_crows',
                              'morning_star', 'evening_star',
                              'head_and_shoulders_top', 'head_and_shoulders_bottom',
                              'double_bottom', 'double_top']

            # 中等信号形态
            medium_patterns = ['bullish_engulfing', 'bearish_engulfing',
                              'ascending_triangle', 'descending_triangle']

            if p_name in strong_patterns:
                if p_signal == 'bullish':
                    buy_score += 3
                    cn_name = CANDLESTICK_NAMES.get(p_name) or CHART_PATTERN_NAMES.get(p_name, p_name)
                    reasons.append(f"🔥 {cn_name}形态，强看涨信号")
                    breakdown.append({'indicator': f'{cn_name}形态', 'value': '', 'signal': '强看涨', 'score': 3})
                elif p_signal == 'bearish':
                    buy_score -= 3
                    cn_name = CANDLESTICK_NAMES.get(p_name) or CHART_PATTERN_NAMES.get(p_name, p_name)
                    reasons.append(f"🔥 {cn_name}形态，强看跌信号")
                    breakdown.append({'indicator': f'{cn_name}形态', 'value': '', 'signal': '强看跌', 'score': -3})
            elif p_name in medium_patterns:
                if p_signal == 'bullish':
                    buy_score += 2
                    cn_name = CANDLESTICK_NAMES.get(p_name) or CHART_PATTERN_NAMES.get(p_name, p_name)
                    reasons.append(f"✅ {cn_name}形态，看涨信号")
                    breakdown.append({'indicator': f'{cn_name}形态', 'value': '', 'signal': '看涨', 'score': 2})
                elif p_signal == 'bearish':
                    buy_score -= 2
                    cn_name = CANDLESTICK_NAMES.get(p_name) or CHART_PATTERN_NAMES.get(p_name, p_name)
                    reasons.append(f"⚠️ {cn_name}形态，看跌信号")
                    breakdown.append({'indicator': f'{cn_name}形态', 'value': '', 'signal': '看跌', 'score': -2})
            else:
                # 弱信号形态（锤子线、十字星等）
                if p_signal == 'bullish':
                    buy_score += 1
                    cn_name = CANDLESTICK_NAMES.get(p_name) or CHART_PATTERN_NAMES.get(p_name, p_name)
                    reasons.append(f"📍 {cn_name}形态出现")
                    breakdown.append({'indicator': f'{cn_name}形态', 'value': '', 'signal': '看涨', 'score': 1})
                elif p_signal == 'bearish':
                    buy_score -= 1
                    cn_name = CANDLESTICK_NAMES.get(p_name) or CHART_PATTERN_NAMES.get(p_name, p_name)
                    reasons.append(f"📍 {cn_name}形态出现")
                    breakdown.append({'indicator': f'{cn_name}形态', 'value': '', 'signal': '看跌', 'score': -1})

    # === 生成建议 (v3.4 调整阈值) ===
    if buy_score >= 6:
        action = "BUY"
        confidence = "高"
    elif buy_score >= 3:
        action = "BUY"
        confidence = "中"
    elif buy_score <= -6:
        action = "SELL"
        confidence = "高"
    elif buy_score <= -3:
        action = "SELL"
        confidence = "中"
    else:
        action = "HOLD"
        confidence = "中"

    # === 计算价格建议 ===
    if atr and atr_percent:
        if atr_percent > 5:
            atr_multiplier = 2.5  # 高波动
        elif atr_percent > 3:
            atr_multiplier = 2.0  # 中等波动
        else:
            atr_multiplier = 1.5  # 低波动

        stop_loss = current_price - atr * atr_multiplier
        take_profit = current_price + atr * atr_multiplier * 2.5
        buy_price = current_price - atr * 0.5
        risk = current_price - stop_loss
        reward = take_profit - current_price
        risk_reward = reward / risk if risk > 0 else 0
    else:
        buy_price = min(current_price * 0.97, bb_lower * 1.02)
        stop_loss = bb_lower * 0.95
        take_profit = bb_upper * 0.95
        risk_reward = None

    # 结合支撑位优化止损
    if nearest_support and stop_loss > nearest_support:
        stop_loss = nearest_support * 0.98  # 支撑位下方 2%

    sell_price = max(current_price * 1.05, bb_upper * 0.98)

    # 结合阻力位优化止盈
    if nearest_resistance and take_profit > nearest_resistance:
        take_profit = nearest_resistance * 0.98  # 阻力位下方 2%

    # 仓位建议
    if confidence == "高":
        suggested_position = 30.0
    elif confidence == "中":
        suggested_position = 20.0
    else:
        suggested_position = 10.0

    # 确定主要背离信号
    divergence_signal = None
    if macd_divergence in ['bullish', 'bearish']:
        divergence_signal = f"MACD_{macd_divergence}"
    elif rsi_divergence in ['bullish', 'bearish']:
        divergence_signal = f"RSI_{rsi_divergence}"

    return TradingSignal(
        action=action,
        confidence=confidence,
        buy_price=round(buy_price, 2),
        sell_price=round(sell_price, 2),
        stop_loss=round(stop_loss, 2),
        take_profit=round(take_profit, 2),
        reasons=reasons,
        # v3.2 字段
        atr=atr,
        atr_percent=atr_percent,
        risk_reward_ratio=round(risk_reward, 2) if risk_reward else None,
        suggested_position=suggested_position,
        volume_signal=volume_signal,
        ma_trend=ma_arrangement,
        # v3.3 新增字段
        kdj_signal=kdj_signal,
        divergence_signal=divergence_signal,
        obv_signal=obv_signal,
        support_price=nearest_support,
        resistance_price=nearest_resistance,
        score=buy_score,
        score_breakdown=breakdown
    )


def format_simple_report(
    ticker: str,
    name: str,
    current_price: float,
    change_pct: float,
    rsi: float,
    macd_histogram: float,
    bb_upper: float,
    bb_middle: float,
    bb_lower: float,
    signal: TradingSignal
) -> str:
    """生成简洁版报告（一屏看完）"""

    # 涨跌颜色
    change_emoji = "🟢" if change_pct >= 0 else "🔴"

    # 信号颜色
    if signal.action == "BUY":
        action_text = "🟢 **建议买入**"
    elif signal.action == "SELL":
        action_text = "🔴 **建议卖出**"
    else:
        action_text = "⚪ **观望等待**"

    report = f"""
## {ticker} ({name}) 简易分析

### 📊 当前状态
- **价格**: ${current_price:.2f} ({change_emoji} {change_pct:+.2f}%)
- **RSI**: {rsi:.1f} {'🟢超卖' if rsi < 30 else '🔴超买' if rsi > 70 else '⚪正常'}
- **MACD**: {'🟢多头' if macd_histogram > 0 else '🔴空头'}
- **位置**: 在布林带 {'下方' if current_price < bb_lower else '上方' if current_price > bb_upper else '中间'}

### 🎯 交易建议
{action_text} (置信度: {signal.confidence})

| 操作 | 建议价格 |
|------|----------|
| 买入价 | ${signal.buy_price:.2f} |
| 止损价 | ${signal.stop_loss:.2f} |
| 止盈价 | ${signal.take_profit:.2f} |

### 📝 理由
"""

    for reason in signal.reasons[:4]:  # 最多显示4条
        report += f"- {reason}\n"

    return report


def format_detailed_report(
    ticker: str,
    name: str,
    current_price: float,
    change_pct: float,
    rsi: float,
    macd_line: float,
    signal_line: float,
    macd_histogram: float,
    prev_macd_histogram: float,
    bb_upper: float,
    bb_middle: float,
    bb_lower: float,
    prices_1m: List[float],
    prices_3m: List[float],
    signal: TradingSignal
) -> str:
    """生成详细版报告"""

    # 基础信息
    change_emoji = "🟢" if change_pct >= 0 else "🔴"

    report = f"""
# {ticker} ({name}) 详细技术分析

---

## 一、价格概览

| 指标 | 数值 |
|------|------|
| 当前价格 | ${current_price:.2f} |
| 今日涨跌 | {change_emoji} {change_pct:+.2f}% |
| 布林带上轨 | ${bb_upper:.2f} |
| 布林带中轨 | ${bb_middle:.2f} |
| 布林带下轨 | ${bb_lower:.2f} |

---

## 二、技术指标解读

### RSI (相对强弱指数)
{explain_rsi_simple(rsi)}

### MACD (指数平滑异同移动平均线)
{explain_macd_simple(macd_line, signal_line, macd_histogram, prev_macd_histogram)}

| MACD 数值 | |
|-----------|--------|
| MACD 线 | {macd_line:.4f} |
| 信号线 | {signal_line:.4f} |
| 柱状图 | {macd_histogram:.4f} |

### 布林带位置
{explain_bollinger_simple(current_price, bb_upper, bb_middle, bb_lower)}

---

## 三、趋势分析

### 近1个月趋势
{explain_trend_simple(prices_1m, "近1个月") if prices_1m else "数据不足"}

### 近3个月趋势
{explain_trend_simple(prices_3m, "近3个月") if prices_3m else "数据不足"}

---

## 四、交易建议

### 综合判断
"""

    if signal.action == "BUY":
        report += "### 🟢 **建议买入**\n\n"
    elif signal.action == "SELL":
        report += "### 🔴 **建议卖出**\n\n"
    else:
        report += "### ⚪ **建议观望**\n\n"

    report += f"**置信度**: {signal.confidence}\n\n"

    report += "**分析理由**:\n"
    for i, reason in enumerate(signal.reasons, 1):
        report += f"{i}. {reason}\n"

    report += f"""
### 价格建议

| 操作类型 | 建议价格 | 说明 |
|----------|----------|------|
| 🟢 买入价 | ${signal.buy_price:.2f} | 建议在此价格附近分批买入 |
| 🔴 止损价 | ${signal.stop_loss:.2f} | 跌破此价应止损离场 |
| 🎯 止盈价 | ${signal.take_profit:.2f} | 涨到此价可考虑部分止盈 |

---

## 五、风险提示

⚠️ **重要提醒**：
1. 以上分析仅供参考，不构成投资建议
2. 股市有风险，投资需谨慎
3. 建议分批建仓，不要一次性满仓
4. 设置好止损，控制风险
5. 技术分析有局限性，需结合基本面和市场环境

---

*分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""

    return report


# ============================================
# v4.0 HTML 报告入口
# ============================================

def generate_html_report(
    ticker: str,
    name: str,
    analysis_result: Dict,
    signal: TradingSignal,
    stock_data: Dict,
    polymarket_data: Optional[Dict] = None,
    report_type: str = 'detailed'
) -> str:
    """
    生成交互式 HTML 报告。

    失败时回退到 format_detailed_report() 并返回 Markdown 字符串。

    返回: HTML 文件的绝对路径（成功时）或 Markdown 字符串（失败时）
    """
    try:
        import sys
        import os as _os
        skill_scripts = _os.path.dirname(_os.path.abspath(__file__))
        if skill_scripts not in sys.path:
            sys.path.insert(0, skill_scripts)
        from html_report import HTMLReportGenerator
        gen = HTMLReportGenerator()
        return gen.generate(
            ticker=ticker,
            name=name,
            analysis_result=analysis_result,
            signal=signal,
            stock_data=stock_data,
            polymarket_data=polymarket_data,
            report_type=report_type
        )
    except Exception as e:
        print(f"[HTML报告] 生成失败，回退到 Markdown: {e}")
        indicators = analysis_result.get('indicators', {})
        macd = indicators.get('macd', {})
        bb = indicators.get('bbands', {})
        prices = analysis_result.get('prices', {})
        return format_detailed_report(
            ticker=ticker,
            name=name,
            current_price=analysis_result.get('current_price', 0),
            change_pct=0,
            rsi=indicators.get('rsi', 50),
            macd_line=macd.get('macd_line', 0),
            signal_line=macd.get('signal_line', 0),
            macd_histogram=macd.get('histogram', 0),
            prev_macd_histogram=macd.get('prev_histogram', 0),
            bb_upper=bb.get('upper', 0) if isinstance(bb, dict) else 0,
            bb_middle=bb.get('middle', 0) if isinstance(bb, dict) else 0,
            bb_lower=bb.get('lower', 0) if isinstance(bb, dict) else 0,
            prices_1m=prices.get('close_1m', []),
            prices_3m=prices.get('close_3m', []),
            signal=signal
        )
