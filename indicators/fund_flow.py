# -*- coding: utf-8 -*-
"""资金流指标：北向资金/两融"""
import numpy as np
import pandas as pd


def north_flow_score(north_df: pd.DataFrame) -> dict:
    """北向资金打分"""
    if north_df.empty or "net_flow" not in north_df.columns:
        return {"score": 0, "detail": "数据缺失"}

    # 近5日净流入
    net_5d = north_df["net_flow"].tail(5).sum() / 1e8
    net_20d = north_df["net_flow"].tail(20).sum() / 1e8

    s = 0
    if net_5d > 50:
        s = 2.5
    elif net_5d > 20:
        s = 1.5
    elif net_5d > 0:
        s = 0.5
    elif net_5d > -20:
        s = -0.5
    elif net_5d > -50:
        s = -1.5
    else:
        s = -2.5

    # 20日趋势加分
    if net_20d > 0 and net_5d > 0:
        s += 0.5

    return {
        "net_5d": round(net_5d, 1),
        "net_20d": round(net_20d, 1),
        "score": round(s, 1),
        "detail": f"北向5日净流入={net_5d:.1f}亿 | 20日={net_20d:.1f}亿",
    }


def fund_flow_score(north_df: pd.DataFrame, margin_df=None) -> dict:
    """综合资金流评分"""
    nf = north_flow_score(north_df)
    total = round(nf["score"], 1)  # 简化版只用北向资金
    return {
        "north_5d": nf.get("net_5d", 0),
        "north_20d": nf.get("net_20d", 0),
        "score": total,
        "detail": nf["detail"],
    }
