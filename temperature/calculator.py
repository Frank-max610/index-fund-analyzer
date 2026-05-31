# -*- coding: utf-8 -*-
"""
指数温度计算器
基于 PE/PB 历史百分位的复合温度（PE权重0.6, PB权重0.4）

参考：长投温度方法论 — PE_Temp = NORMDIST(当前PE, 均值, 标准差)
本实现使用百分位法（更稳健，不受PE分布偏态影响）：
  PE_Temp = (历史PE < 当前PE 的天数) / 总天数 × 100
  PB_Temp = (历史PB < 当前PB 的天数) / 总天数 × 100
  Composite = PE_Temp × 0.6 + PB_Temp × 0.4
"""

import numpy as np
import pandas as pd
from config import TEMPERATURE_CONFIG, WATCH_INDICES


def compute_index_temperature(
    pe_series: np.ndarray,
    pb_series: np.ndarray,
    current_pe: float,
    current_pb: float,
    pe_weight: float = None,
    pb_weight: float = None,
) -> dict:
    """
    计算单个指数的PE/PB复合温度。

    Args:
        pe_series: 历史PE序列（5年日频数据）
        pb_series: 历史PB序列
        current_pe: 当前PE值
        current_pb: 当前PB值
        pe_weight: PE权重（默认从config读取）
        pb_weight: PB权重（默认从config读取）

    Returns:
        {
            "pe_temperature": float,       # PE分位温度 (0-100)
            "pb_temperature": float,       # PB分位温度 (0-100)
            "composite_temperature": float, # 复合温度 (0-100)
            "pe_percentile": float,
            "pb_percentile": float,
            "pe_current": float,
            "pb_current": float,
            "pe_median": float,
            "pb_median": float,
            "data_points": int,
            "status": str,                 # "ok" | "insufficient_data" | "pe_only" | "pb_only"
        }
    """
    if pe_weight is None:
        pe_weight = TEMPERATURE_CONFIG["pe_weight"]
    if pb_weight is None:
        pb_weight = TEMPERATURE_CONFIG["pb_weight"]

    min_points = TEMPERATURE_CONFIG["min_data_points"]

    # 清理数据
    pe_clean = pe_series[np.isfinite(pe_series)] if pe_series is not None else np.array([])
    pb_clean = pb_series[np.isfinite(pb_series)] if pb_series is not None else np.array([])

    has_pe = len(pe_clean) >= min_points and current_pe is not None and np.isfinite(current_pe)
    has_pb = len(pb_clean) >= min_points and current_pb is not None and np.isfinite(current_pb)

    result = {
        "pe_temperature": None,
        "pb_temperature": None,
        "composite_temperature": None,
        "pe_percentile": None,
        "pb_percentile": None,
        "pe_current": round(float(current_pe), 4) if current_pe and np.isfinite(current_pe) else None,
        "pb_current": round(float(current_pb), 4) if current_pb and np.isfinite(current_pb) else None,
        "pe_median": None,
        "pb_median": None,
        "data_points": max(len(pe_clean), len(pb_clean)),
        "status": "insufficient_data",
    }

    # 计算PE温度
    if has_pe:
        pe_temp = np.sum(pe_clean < current_pe) / len(pe_clean) * 100
        result["pe_temperature"] = round(float(pe_temp), 1)
        result["pe_percentile"] = round(float(pe_temp), 1)
        result["pe_median"] = round(float(np.median(pe_clean)), 4)

    # 计算PB温度
    if has_pb:
        pb_temp = np.sum(pb_clean < current_pb) / len(pb_clean) * 100
        result["pb_temperature"] = round(float(pb_temp), 1)
        result["pb_percentile"] = round(float(pb_temp), 1)
        result["pb_median"] = round(float(np.median(pb_clean)), 4)

    # 计算复合温度
    if has_pe and has_pb:
        composite = result["pe_temperature"] * pe_weight + result["pb_temperature"] * pb_weight
        result["composite_temperature"] = round(composite, 1)
        result["status"] = "ok"
    elif has_pe and not has_pb:
        result["composite_temperature"] = result["pe_temperature"]
        result["status"] = "pe_only"
    elif has_pb and not has_pe:
        result["composite_temperature"] = result["pb_temperature"]
        result["status"] = "pb_only"
    else:
        result["status"] = "insufficient_data"

    return result


def compute_all_temperatures(
    pe_pb_data: dict,   # {index_code: {pe: float, pb: float, pe_series: [...], pb_series: [...]}}
    kline_data: dict = None,  # {index_code: {close: float, closes: [...]}} 备用：价格分位温度
) -> dict:
    """
    批量计算所有监控指数的温度。

    Args:
        pe_pb_data: 各指数的PE/PB数据（来自 data/fetcher 的 legulegu 接口）
        kline_data: 各指数的K线数据（备用，当PE/PB不可用时计算价格分位温度）

    Returns:
        {index_code: temperature_result_dict}
    """
    results = {}

    for idx_cfg in WATCH_INDICES:
        code = idx_cfg["code"]
        name = idx_cfg["name"]

        # 确定数据查询码（红利低波用中证红利代理）
        lookup_code = idx_cfg.get("proxy_code", code)

        pe_pb = pe_pb_data.get(lookup_code, {}) if pe_pb_data else {}

        pe_series_raw = pe_pb.get("pe_series", [])
        pb_series_raw = pe_pb.get("pb_series", [])
        current_pe = pe_pb.get("pe")
        current_pb = pe_pb.get("pb")

        pe_series = np.array(pe_series_raw) if isinstance(pe_series_raw, list) else pe_series_raw
        pb_series = np.array(pb_series_raw) if isinstance(pb_series_raw, list) else pb_series_raw

        temp_result = compute_index_temperature(
            pe_series=pe_series,
            pb_series=pb_series,
            current_pe=current_pe,
            current_pb=current_pb,
        )

        # 如果PE/PB数据不足，尝试用价格分位温度作为备用
        if temp_result["status"] == "insufficient_data" and kline_data:
            kl = kline_data.get(code, {}) or kline_data.get(lookup_code, {})
            closes = kl.get("closes", [])
            current_close = kl.get("close")
            if closes and current_close and len(closes) >= TEMPERATURE_CONFIG["min_data_points"]:
                price_temp = sum(1 for c in closes if c < current_close) / len(closes) * 100
                temp_result["composite_temperature"] = round(price_temp, 1)
                temp_result["status"] = "price_only"

        temp_result["index_name"] = name
        temp_result["index_code"] = code
        temp_result["lookup_code"] = lookup_code
        results[code] = temp_result

    return results
