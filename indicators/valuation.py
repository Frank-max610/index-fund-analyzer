# -*- coding: utf-8 -*-
"""估值指标：PE/PB/分位/股债利差/PEG/E/P"""
import numpy as np
import pandas as pd


def pe_percentile_score(pe: float, pe_percentile: float) -> float:
    """PE分位打分：分位越低估值越低→买入信号越强"""
    if pe_percentile <= 0.10:
        return 3.0
    elif pe_percentile <= 0.20:
        return 2.0
    elif pe_percentile <= 0.35:
        return 1.0
    elif pe_percentile <= 0.65:
        return 0.0
    elif pe_percentile <= 0.80:
        return -1.0
    elif pe_percentile <= 0.90:
        return -2.0
    else:
        return -3.0


def pb_percentile_score(pb_percentile: float) -> float:
    """PB分位打分"""
    return pe_percentile_score(0, pb_percentile)  # 复用相同分位逻辑


def equity_bond_spread(ep: float, bond_yield: float) -> float:
    """股债利差 = 盈利收益率 - 10年期国债收益率"""
    return ep - bond_yield


def spread_score(spread: float) -> float:
    """股债利差打分：
    > 3% : 极度低估 +3
    2~3% : 低估 +2
    1~2% : 略低 +1
    0~1% : 中性  0
    -1~0% : 略贵 -1
    <-1% : 高估 -2
    """
    if spread >= 0.03:
        return 3.0
    elif spread >= 0.02:
        return 2.0
    elif spread >= 0.01:
        return 1.0
    elif spread >= 0:
        return 0.0
    elif spread >= -0.01:
        return -1.0
    else:
        return -2.0


def valuation_score(pe: float, pe_pct: float, pb_pct: float,
                    bond_yield: float) -> dict:
    """综合估值评分"""
    ep = 1.0 / pe if pe > 0 else 0.05
    spread = equity_bond_spread(ep, bond_yield)

    s_pe = pe_percentile_score(pe, pe_pct)
    s_pb = pb_percentile_score(pb_pct)
    s_spread = spread_score(spread)

    # 综合：PE分位权重0.4 + PB分位0.2 + 股债利差0.4
    total = round(s_pe * 0.4 + s_pb * 0.2 + s_spread * 0.4, 1)

    return {
        "pe": round(pe, 2),
        "pe_percentile": round(pe_pct * 100, 1),
        "pb_percentile": round(pb_pct * 100, 1),
        "ep": round(ep * 100, 2),
        "bond_yield": round(bond_yield, 2),
        "spread": round(spread * 100, 2),
        "score": total,
        "detail": (
            f"PE={pe:.1f}({pe_pct*100:.0f}%分位) | "
            f"股债利差={spread*100:.1f}% | "
            f"PB分位={pb_pct*100:.0f}%"
        ),
    }
