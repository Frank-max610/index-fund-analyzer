# -*- coding: utf-8 -*-
"""风险指标：波动率/最大回撤/夏普比率/VaR"""
import numpy as np
import pandas as pd


def max_drawdown(close: pd.Series) -> float:
    cummax = close.expanding().max()
    drawdown = (close - cummax) / cummax
    return float(drawdown.min())


def volatility(close: pd.Series, period=20) -> float:
    ret = close.pct_change().dropna()
    return float(ret.tail(period).std() * np.sqrt(252))


def downside_vol(close: pd.Series, period=60) -> float:
    ret = close.pct_change().dropna().tail(period)
    neg_ret = ret[ret < 0]
    return float(neg_ret.std() * np.sqrt(252)) if len(neg_ret) > 0 else 0.1


def var_95(close: pd.Series, period=60) -> float:
    ret = close.pct_change().dropna().tail(period)
    return float(np.percentile(ret, 5))


def sharpe_ratio(close: pd.Series, risk_free=0.025, period=120) -> float:
    ret = close.pct_change().dropna().tail(period)
    excess = ret.mean() * 252 - risk_free
    vol = ret.std() * np.sqrt(252)
    return float(excess / vol) if vol > 0 else 0


def risk_score(close: pd.Series) -> dict:
    """风险打分"""
    if len(close) < 60:
        return {"score": 0, "detail": "数据不足"}

    vol = volatility(close)
    mdd = max_drawdown(close)
    sharpe = sharpe_ratio(close)

    # 波动率低→得分高（风险低）
    s_vol = 0
    if vol < 0.15:
        s_vol = 1.5
    elif vol < 0.20:
        s_vol = 1
    elif vol < 0.25:
        s_vol = 0
    elif vol < 0.35:
        s_vol = -1
    else:
        s_vol = -2

    # 回撤小→得分高
    s_mdd = 0
    if mdd > -0.10:
        s_mdd = 1
    elif mdd > -0.20:
        s_mdd = 0
    elif mdd > -0.30:
        s_mdd = -1
    else:
        s_mdd = -2

    # 夏普高→得分高
    s_sharpe = 0
    if sharpe > 1.5:
        s_sharpe = 2
    elif sharpe > 0.8:
        s_sharpe = 1
    elif sharpe > 0.3:
        s_sharpe = 0
    elif sharpe > -0.3:
        s_sharpe = -1
    else:
        s_sharpe = -2

    total = round(s_vol * 0.35 + s_mdd * 0.35 + s_sharpe * 0.3, 1)

    return {
        "volatility": round(vol * 100, 1),
        "max_drawdown": round(mdd * 100, 1),
        "sharpe": round(sharpe, 2),
        "score": total,
        "detail": (
            f"年化波动率={vol*100:.1f}% | "
            f"最大回撤={mdd*100:.1f}% | 夏普比={sharpe:.2f}"
        ),
    }
