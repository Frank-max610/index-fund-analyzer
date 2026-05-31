# -*- coding: utf-8 -*-
"""
阈值规则引擎 — 严格执行定稿规范中的指数温度交易策略

硬性规则（零主观判断）：
1. 主力标的判定：
   - A500 温度 < 30% → 主力切换为 A500
   - A500 温度 >= 30% → 主力为 红利低波

2. 主力标的操作：
   - 温度 < 50% → 正常每日10元定投
   - 50% <= 温度 <= 80% → 维持持仓，正常定投
   - 温度 > 80% → 暂停定投，仅持有

3. 特殊观察：
   - 沪深300 温度 < 20% → 抄底布局信号
   - 中证500 温度 < 15% → 严重低估参考
"""

from config import THRESHOLDS, BASE_AMOUNT, WATCH_INDICES


def decide_daily_action(temperatures: dict) -> dict:
    """
    根据各指数温度，输出每日操作决策。

    Args:
        temperatures: {index_code: {composite_temperature: float, ...}}
                      来自 temperature.calculator.compute_all_temperatures

    Returns:
        {
            "date": str,
            "primary_target": str,        # 主力定投标的 index_code
            "primary_name": str,
            "primary_fund_code": str,     # 对应基金代码
            "primary_temperature": float,
            "action": str,                # "DCA_NORMAL" | "DCA_PAUSE"
            "action_label": str,          # 人类可读标签
            "amount": float,              # 建议投入金额（0或10）
            "switch_reason": str | None,  # 切换原因
            "alerts": [str],              # 特殊提醒列表
            "all_signals": {index_code: signal_dict},  # 每个标的的信号详情
        }
    """
    # 提取各指数温度
    def _temp(code):
        t = temperatures.get(code, {})
        return t.get("composite_temperature")

    t_h30269 = _temp("H30269")
    t_a500 = _temp("000510")
    t_hs300 = _temp("000300")
    t_zz500 = _temp("000905")

    alerts = []
    switch_reason = None
    all_signals = {}

    # ═══════════════════════════════════════
    # 规则1: 判定主力标的（A500切换规则）
    # ═══════════════════════════════════════
    if t_a500 is not None and t_a500 < THRESHOLDS["a500_switch"]:
        primary = "000510"
        primary_name = "中证A500"
        primary_fund = None  # A500暂无联接基金代码，标记为指数观察
        primary_temp = t_a500
        switch_reason = f"中证A500温度 {t_a500}% < 切换线 {THRESHOLDS['a500_switch']}%，主力切换至A500"
        alerts.append(switch_reason)
    else:
        primary = "H30269"
        primary_name = "中证红利低波"
        primary_fund = "007466"
        primary_temp = t_h30269
        if t_a500 is not None and t_a500 >= THRESHOLDS["a500_switch"]:
            # 之前切换过，现在切回
            pass  # 正常状态，无需额外提醒

    # ═══════════════════════════════════════
    # 规则2: 主力标的操作判定
    # ═══════════════════════════════════════
    if primary_temp is None:
        # 数据缺失，保守处理：按正常定投
        action = "DCA_NORMAL"
        action_label = "正常定投（数据缺失，保守处理）"
        amount = BASE_AMOUNT
        alerts.append(f"{primary_name}温度数据缺失，按正常定投处理")
    elif primary_temp < THRESHOLDS["primary_dca"]:
        action = "DCA_NORMAL"
        action_label = f"正常定投（温度 {primary_temp}% < {THRESHOLDS['primary_dca']}%）"
        amount = BASE_AMOUNT
    elif primary_temp <= THRESHOLDS["primary_hold"]:
        action = "DCA_NORMAL"
        action_label = f"持有+定投（温度 {primary_temp}% 在 {THRESHOLDS['primary_dca']}%-{THRESHOLDS['primary_hold']}%）"
        amount = BASE_AMOUNT
    else:
        action = "DCA_PAUSE"
        action_label = f"暂停定投（温度 {primary_temp}% > {THRESHOLDS['primary_pause']}%，仅持有现有份额）"
        amount = 0
        alerts.append(f"{primary_name}温度过高（{primary_temp}%），暂停新增买入")

    # ═══════════════════════════════════════
    # 规则3: 特殊观察信号
    # ═══════════════════════════════════════
    if t_hs300 is not None and t_hs300 < THRESHOLDS["hs300_bottom"]:
        msg = f"沪深300温度 {t_hs300}% < 抄底线 {THRESHOLDS['hs300_bottom']}%，可用资金抄底布局"
        alerts.append(msg)

    if t_zz500 is not None and t_zz500 < THRESHOLDS["zz500_deep_value"]:
        msg = f"中证500温度 {t_zz500}% < 严重低估线 {THRESHOLDS['zz500_deep_value']}%，可小仓位布局"
        alerts.append(msg)

    # ═══════════════════════════════════════
    # 构建各标的信号详情
    # ═══════════════════════════════════════
    for idx_cfg in WATCH_INDICES:
        code = idx_cfg["code"]
        name = idx_cfg["name"]
        temp = _temp(code)

        if temp is None:
            signal = "数据缺失"
            signal_emoji = "⚪"
        elif code == primary:
            signal = action_label
            signal_emoji = "🟢" if action == "DCA_NORMAL" else "🔴"
        elif code == "000510" and temp < THRESHOLDS["a500_switch"]:
            signal = f"切换信号触发（{temp}% < {THRESHOLDS['a500_switch']}%）"
            signal_emoji = "🟡"
        elif code == "000300" and temp < THRESHOLDS["hs300_bottom"]:
            signal = f"抄底信号（{temp}% < {THRESHOLDS['hs300_bottom']}%）"
            signal_emoji = "🔵"
        elif code == "000905" and temp < THRESHOLDS["zz500_deep_value"]:
            signal = f"严重低估（{temp}% < {THRESHOLDS['zz500_deep_value']}%）"
            signal_emoji = "🟣"
        elif temp < 50:
            signal = "低估区间"
            signal_emoji = "🟢"
        elif temp <= 80:
            signal = "合理区间"
            signal_emoji = "🟡"
        else:
            signal = "高估区间"
            signal_emoji = "🔴"

        all_signals[code] = {
            "name": name,
            "temperature": temp,
            "signal": signal,
            "emoji": signal_emoji,
        }

    return {
        "primary_target": primary,
        "primary_name": primary_name,
        "primary_fund_code": primary_fund,
        "primary_temperature": primary_temp,
        "action": action,
        "action_label": action_label,
        "amount": amount,
        "switch_reason": switch_reason,
        "alerts": alerts,
        "all_signals": all_signals,
    }


class ThresholdEngine:
    """阈值规则引擎（有状态版本，用于后续扩展）"""

    def __init__(self):
        self.thresholds = THRESHOLDS
        self.base_amount = BASE_AMOUNT

    def decide(self, temperatures: dict) -> dict:
        return decide_daily_action(temperatures)
