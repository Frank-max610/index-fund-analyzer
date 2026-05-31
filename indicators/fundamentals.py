# -*- coding: utf-8 -*-
"""基本面指标：ROE/增速/盈利稳定性"""
import numpy as np
import pandas as pd


def fundamentals_score(close: pd.Series) -> dict:
    """基本面评分（简化版：基于价格动量推断盈利质量）"""
    if len(close) < 120:
        return {"score": 0, "detail": "数据不足"}

    # 长期趋势强度
    ret_60d = (close.iloc[-1] / close.iloc[-60] - 1)
    ret_120d = (close.iloc[-1] / close.iloc[-120] - 1)

    # 盈利稳定性：日收益率标准差越小越稳定
    daily_ret = close.pct_change().dropna()
    stability = 1.0 - min(daily_ret.tail(60).std() * np.sqrt(252) / 0.3, 1.0)

    s_trend = 0
    if ret_120d > 0.15:
        s_trend = 2
    elif ret_120d > 0.05:
        s_trend = 1
    elif ret_120d > -0.05:
        s_trend = 0
    elif ret_120d > -0.15:
        s_trend = -1
    else:
        s_trend = -2

    s_stab = 0
    if stability > 0.8:
        s_stab = 1
    elif stability > 0.6:
        s_stab = 0.5
    elif stability > 0.4:
        s_stab = 0
    else:
        s_stab = -1

    total = round(s_trend * 0.6 + s_stab * 0.4, 1)

    return {
        "ret_60d": round(ret_60d * 100, 1),
        "ret_120d": round(ret_120d * 100, 1),
        "stability": round(stability, 2),
        "score": total,
        "detail": (
            f"60日收益={ret_60d*100:.1f}% | "
            f"120日收益={ret_120d*100:.1f}% | "
            f"稳定性={stability:.2f}"
        ),
    }
