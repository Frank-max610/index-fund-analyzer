# -*- coding: utf-8 -*-
"""情绪指标：涨跌比/恐惧贪婪"""
import numpy as np
import pandas as pd


def sentiment_score(market_stats: dict, close: pd.Series = None) -> dict:
    """情绪打分"""
    # 上涨占比
    up_ratio = market_stats.get("up_ratio", 0.5)
    s_ratio = 0
    if up_ratio > 0.70:
        s_ratio = -2  # 过热
    elif up_ratio > 0.58:
        s_ratio = -0.5
    elif up_ratio > 0.42:
        s_ratio = 0
    elif up_ratio > 0.30:
        s_ratio = 0.5
    else:
        s_ratio = 2  # 恐慌→机会

    # 短期涨跌幅：连跌后情绪修复机会
    s_ret = 0
    if close is not None and len(close) >= 5:
        ret_5d = (close.iloc[-1] / close.iloc[-5] - 1)
        if ret_5d < -0.05:
            s_ret = 1.5
        elif ret_5d < -0.03:
            s_ret = 1
        elif ret_5d > 0.05:
            s_ret = -1
        elif ret_5d > 0.03:
            s_ret = -0.5

    total = round(s_ratio * 0.5 + s_ret * 0.5, 1)

    return {
        "up_ratio": round(up_ratio * 100, 1),
        "ret_5d": round(ret_5d * 100, 1) if close is not None else None,
        "score": total,
        "detail": f"上涨占比={up_ratio*100:.1f}% | 5日收益={ret_5d*100:.1f}%",
    }
