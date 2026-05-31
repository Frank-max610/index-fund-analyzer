# -*- coding: utf-8 -*-
"""技术指标：均线/RSI/MACD/布林/量价"""
import numpy as np
import pandas as pd


def ma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    """返回 (DIF, DEA, MACD柱)"""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    macd_bar = 2 * (dif - dea)
    return dif, dea, macd_bar


def bollinger(close: pd.Series, period=20, std=2):
    mid = ma(close, period)
    std_val = close.rolling(period).std()
    upper = mid + std * std_val
    lower = mid - std * std_val
    return upper, mid, lower


def atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def volume_ratio(volume: pd.Series, period=5):
    return volume / volume.rolling(period).mean()


def technical_score(close: pd.Series, high: pd.Series,
                    low: pd.Series, volume: pd.Series) -> dict:
    """综合技术面打分"""
    if len(close) < 60:
        return {"score": 0, "detail": "数据不足"}

    latest = close.iloc[-1]

    # 1. 均线偏离 (MA20, MA60, MA120)
    ma20 = ma(close, 20).iloc[-1]
    ma60 = ma(close, 60).iloc[-1]
    bias_20 = (latest - ma20) / ma20

    s_ma = 0
    if bias_20 < -0.05:
        s_ma = 2  # 远离均线下方→超卖反弹
    elif bias_20 < -0.02:
        s_ma = 1
    elif bias_20 > 0.05:
        s_ma = -2
    elif bias_20 > 0.02:
        s_ma = -1

    # 均线多头排列加分
    if ma20 > ma60:
        s_ma += 0.5

    # 2. RSI(14)
    rsi_val = rsi(close, 14).iloc[-1]
    s_rsi = 0
    if pd.isna(rsi_val):
        s_rsi = 0
    elif rsi_val < 25:
        s_rsi = 3
    elif rsi_val < 35:
        s_rsi = 1.5
    elif rsi_val < 45:
        s_rsi = 0.5
    elif rsi_val < 55:
        s_rsi = 0
    elif rsi_val < 70:
        s_rsi = -1
    else:
        s_rsi = -2

    # 3. MACD
    dif, dea, bar = macd(close)
    s_macd = 0
    if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
        s_macd = 2  # 金叉
    elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
        s_macd = -2  # 死叉
    elif dif.iloc[-1] > dea.iloc[-1]:
        s_macd = 1
    else:
        s_macd = -1

    # 4. 布林带位置
    upper, mid, lower = bollinger(close)
    u, m, l = upper.iloc[-1], mid.iloc[-1], lower.iloc[-1]
    band_pos = (latest - l) / (u - l) if u != l else 0.5
    s_bb = 0
    if band_pos < 0.1:
        s_bb = 2
    elif band_pos < 0.3:
        s_bb = 1
    elif band_pos > 0.9:
        s_bb = -2
    elif band_pos > 0.7:
        s_bb = -1

    # 5. 量价配合
    vol_ratio = volume_ratio(volume).iloc[-1]
    daily_ret = close.pct_change().iloc[-1]
    s_vol = 0
    if daily_ret > 0 and vol_ratio > 1.3:
        s_vol = 1  # 放量上涨
    elif daily_ret < 0 and vol_ratio > 1.3:
        s_vol = -1  # 放量下跌
    elif daily_ret > 0 and vol_ratio < 0.7:
        s_vol = -0.5  # 缩量上涨→动能不足

    # 综合加权
    total = round(s_ma * 0.2 + s_rsi * 0.2 + s_macd * 0.2 +
                  s_bb * 0.2 + s_vol * 0.2, 1)

    return {
        "bias_20": round(bias_20 * 100, 1),
        "rsi_14": round(rsi_val, 1) if not pd.isna(rsi_val) else None,
        "macd_signal": "金叉" if s_macd > 0 else "死叉" if s_macd < 0 else "中性",
        "bb_position": round(band_pos * 100, 0),
        "vol_ratio": round(vol_ratio, 1),
        "score": total,
        "detail": (
            f"BIAS20={bias_20*100:.1f}% | RSI={rsi_val:.0f} | "
            f"MACD{'金叉' if s_macd>0 else '死叉'} | "
            f"布林位置={band_pos*100:.0f}% | 量比={vol_ratio:.1f}"
        ),
    }
