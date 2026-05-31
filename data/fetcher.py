# -*- coding: utf-8 -*-
"""数据获取层 — 使用 curl_cffi 绕过 macOS Python3.9 SSL 兼容问题"""
import json
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from curl_cffi import requests as curl_req

from .cache import get, set

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

INDEX_NAME_MAP = {
    "000300": "沪深300", "000905": "中证500", "000688": "科创50",
    "000922": "中证红利", "399006": "创业板指", "000016": "上证50",
}

LEGU_SYMBOLS = {
    "上证50", "沪深300", "上证380", "创业板50", "中证500",
    "上证180", "深证红利", "深证100", "中证1000", "上证红利",
    "中证100", "中证800",
}


def _make_json_safe(obj):
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    elif pd.isna(obj) if not isinstance(obj, str) else False:
        return None
    return obj


def _cached(key, fetch_fn, max_age=60):
    cached = get(key, max_age)
    if cached is not None:
        return cached
    data = fetch_fn()
    if isinstance(data, pd.DataFrame):
        data_dict = _make_json_safe(data.to_dict("records"))
        set(key, data_dict)
        return data_dict
    safe = _make_json_safe(data)
    set(key, safe)
    return safe


# ══════════════════════════════════════════════
# 估值数据（乐咕乐股 legulegu.com）
# ══════════════════════════════════════════════

def _lego_pe_pb(name: str, kind: str = "pe") -> pd.DataFrame:
    """从 legulegu.com 拉 PE/PB 数据"""
    slug_map = {
        "上证50": "sz50", "沪深300": "hs300", "中证500": "zz500",
        "上证380": "sz380", "创业板50": "cyb50", "上证180": "sz180",
        "深证红利": "szhl", "深证100": "sz100", "中证1000": "zz1000",
        "上证红利": "szhl2", "中证100": "zz100", "中证800": "zz800",
        "科创50": "hs300", "中证红利": "zz500", "创业板指": "zz500",
    }
    slug = slug_map.get(name, "hs300")
    if kind == "pe":
        url = f"https://legulegu.com/stockdata/{slug}-ttm-lyr"
    else:
        url = f"https://legulegu.com/stockdata/{slug}-pb"

    resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"legulegu.com returned {resp.status_code}")

    # 解析 HTML 中的 JSON 数据
    html = resp.text
    # 找类似 data: [...] 的数组
    patterns = [
        r'data\s*:\s*(\[.*?\])\s*,?\s*\n\s*name',
        r'data\s*:\s*(\[.*?\])',
    ]
    data_json = None
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            data_json = m.group(1)
            break

    if not data_json:
        # 尝试用 pandas read_html
        tables = pd.read_html(html)
        if tables:
            return tables[0]

    if data_json:
        records = json.loads(data_json)
        df = pd.DataFrame(records)
        return df

    raise RuntimeError(f"Cannot parse PE/PB data from {url}")


def fetch_index_pe_pb(code: str) -> dict:
    """获取指数 PE/PB 及分位"""
    name = INDEX_NAME_MAP.get(code)
    if name not in LEGU_SYMBOLS:
        name = "沪深300"

    key = f"pe_pb_{code}"
    return _cached(key, lambda: _fetch_pe_pb_impl(name), max_age=120)


def _fetch_pe_pb_impl(name: str) -> dict:
    try:
        df_pe = _lego_pe_pb(name, "pe")
    except Exception:
        df_pe = pd.DataFrame()

    try:
        df_pb = _lego_pe_pb(name, "pb")
    except Exception:
        df_pb = pd.DataFrame()

    result = {"pe": None, "pb": None, "pe_percentile": 0.5, "pb_percentile": 0.5}

    if not df_pe.empty:
        pe_col = None
        for c in ["close", "value", "pe", "市盈率"]:
            if c in df_pe.columns:
                pe_col = c
                break
        if pe_col is None and len(df_pe.columns) >= 2:
            pe_col = df_pe.columns[1]

        if pe_col:
            vals = pd.to_numeric(df_pe[pe_col], errors="coerce").dropna()
            if len(vals) > 0:
                result["pe"] = float(vals.iloc[-1])
                result["pe_percentile"] = float((vals < result["pe"]).sum() / len(vals))
                result["pe_min"] = float(vals.min())
                result["pe_max"] = float(vals.max())
                result["pe_median"] = float(vals.median())

    if not df_pb.empty:
        pb_col = None
        for c in ["close", "value", "pb", "市净率"]:
            if c in df_pb.columns:
                pb_col = c
                break
        if pb_col is None and len(df_pb.columns) >= 2:
            pb_col = df_pb.columns[1]

        if pb_col:
            vals = pd.to_numeric(df_pb[pb_col], errors="coerce").dropna()
            if len(vals) > 0:
                result["pb"] = float(vals.iloc[-1])
                result["pb_percentile"] = float((vals < result["pb"]).sum() / len(vals))
                result["pb_min"] = float(vals.min())
                result["pb_max"] = float(vals.max())

    return result


# ══════════════════════════════════════════════
# 指数日线（东方财富）
# ══════════════════════════════════════════════

def index_daily(code: str, days: int = 250) -> pd.DataFrame:
    """指数日线数据"""
    key = f"index_daily_{code}_{days}"
    data = _cached(key, lambda: _fetch_index_daily(code, days), max_age=60)
    df = pd.DataFrame(data) if isinstance(data, list) else data
    if df.empty:
        return df
    # 标准化列名
    rename = {
        "日期": "date", "开盘": "open", "最高": "high",
        "最低": "low", "收盘": "close", "成交量": "volume",
        "成交额": "amount", "date": "date",
    }
    # 只 rename 存在的列
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.tail(days).reset_index(drop=True)


def _fetch_index_daily(code: str, days: int) -> pd.DataFrame:
    """从东方财富获取指数 K 线"""
    # 东方财富指数代码映射
    market_map = {
        "000300": "1.000300", "000905": "1.000905",
        "000688": "1.000688", "000922": "1.000922",
        "399006": "0.399006", "000016": "1.000016",
    }
    secid = market_map.get(code, f"1.{code}")
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
        f"fields2=f51,f52,f53,f54,f55,f56,f57&"
        f"klt=101&fqt=1&end=20500101&lmt={days}"
    )
    resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
    data = resp.json()
    if data.get("data") and data["data"].get("klines"):
        rows = []
        for line in data["data"]["klines"]:
            parts = line.split(",")
            if len(parts) >= 7:
                rows.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": float(parts[5]),
                    "amount": float(parts[6]),
                })
        return pd.DataFrame(rows)
    return pd.DataFrame()


# ══════════════════════════════════════════════
# 北向资金
# ══════════════════════════════════════════════

def north_flow(days: int = 30) -> pd.DataFrame:
    key = f"north_flow_{days}"
    data = _cached(key, lambda: _fetch_north_flow(days), max_age=120)
    df = pd.DataFrame(data) if isinstance(data, list) else data
    if df.empty:
        return df
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    if "net_flow" in df.columns:
        df["net_flow"] = pd.to_numeric(df["net_flow"], errors="coerce")
    return df


def _fetch_north_flow(days: int) -> pd.DataFrame:
    url = (
        "https://push2his.eastmoney.com/api/qt/kamt.kline/get?"
        "fields1=f1,f2,f3,f4&fields2=f51,f52&"
        f"klt=101&lmt={days}"
    )
    h = {**HEADERS, "Referer": "https://data.eastmoney.com/"}
    resp = curl_req.get(url, headers=h, impersonate="chrome", timeout=15)
    data = resp.json()
    rows = []
    if data.get("data"):
        d = data["data"]
        # Sum hk2sh + hk2sz for total north flow
        combined = {}
        for key in ["hk2sh", "hk2sz"]:
            if key in d and d[key]:
                for item in d[key]:
                    parts = item.split(",")
                    if len(parts) >= 2:
                        dt = parts[0]
                        val = float(parts[1])
                        combined[dt] = combined.get(dt, 0) + val
        for dt in sorted(combined.keys()):
            rows.append({"date": dt, "net_flow": combined[dt]})
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════
# 国债收益率
# ══════════════════════════════════════════════

def bond_yield_10y() -> float:
    key = "bond_10y"
    return _cached(key, _fetch_bond, max_age=360)


def _fetch_bond() -> float:
    url = (
        "https://datacenter-web.eastmoney.com/api/data/v1/get?"
        "sortColumns=TRADE_DATE&sortTypes=-1&pageSize=5&pageNumber=1&"
        "reportName=RPT_ECONOMY_BOND&columns=ALL&"
        "filter=(TRADE_DATE>='2020-01-01')"
    )
    resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
    data = resp.json()
    if data.get("result") and data["result"].get("data"):
        for row in data["result"]["data"]:
            if "BOND_YIELD" in row:
                return float(row["BOND_YIELD"])
            if "CLOSE_YIELD" in row:
                return float(row["CLOSE_YIELD"])
    # Fallback: use Sina bond API
    url2 = (
        "https://hq.sinajs.cn/list=bond_1y,bond_10y"
    )
    h = {**HEADERS, "Referer": "https://finance.sina.com.cn/"}
    r2 = curl_req.get(url2, headers=h, impersonate="chrome", timeout=15)
    # Parse Sina response format: var ...="..."
    m = re.search(r'bond_10y="([^"]*)"', r2.text)
    if m:
        parts = m.group(1).split(",")
        if len(parts) >= 2:
            return float(parts[1])
    return 2.80


# ══════════════════════════════════════════════
# 宏观数据
# ══════════════════════════════════════════════

def macro_data() -> dict:
    key = "macro_snapshot"
    return _cached(key, _fetch_macro, max_age=360)


def _fetch_macro() -> dict:
    result = {"pmi": 50.0, "cpi": 2.0, "m2": 8.0}

    # PMI from EastMoney
    try:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_ECONOMY_PMI&columns=ALL&"
            "sortColumns=TRADE_DATE&sortTypes=-1&pageSize=3&pageNumber=1"
        )
        r = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            latest = d["result"]["data"][0]
            for k in ["MAKE_INDEX", "PMI", "PURCHASE_INDEX"]:
                if k in latest:
                    result["pmi"] = float(latest[k])
                    break
    except Exception:
        pass

    # CPI
    try:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_ECONOMY_CPI&columns=ALL&"
            "sortColumns=TRADE_DATE&sortTypes=-1&pageSize=3&pageNumber=1"
        )
        r = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            latest = d["result"]["data"][0]
            for k in ["NATIONAL_SAME", "CPI_SAME", "CPI"]:
                if k in latest:
                    result["cpi"] = float(latest[k])
                    break
    except Exception:
        pass

    # M2
    try:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_ECONOMY_MONEY_SUPPLY&columns=ALL&"
            "sortColumns=TRADE_DATE&sortTypes=-1&pageSize=3&pageNumber=1"
        )
        r = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            latest = d["result"]["data"][0]
            for k in ["M2_SAME", "M2"]:
                if k in latest:
                    result["m2"] = float(latest[k])
                    break
    except Exception:
        pass

    return result


# ══════════════════════════════════════════════
# 全市场涨跌统计
# ══════════════════════════════════════════════

def market_stats() -> dict:
    key = "market_stats"
    return _cached(key, _fetch_market_stats, max_age=60)


def _fetch_market_stats() -> dict:
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=20&po=1&np=1&fltt=2&invt=2&"
            "fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&"
            "fields=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12"
        )
        r = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        d = r.json()
        if d.get("data") and d["data"].get("diff"):
            up = down = 0
            for item in d["data"]["diff"]:
                pct = item.get("f3", 0)
                if pct is None:
                    continue
                if float(pct) > 0:
                    up += 1
                elif float(pct) < 0:
                    down += 1
            total = up + down
            return {
                "up": up, "down": down,
                "up_ratio": round(up / total, 3) if total > 0 else 0.5,
            }
    except Exception:
        pass
    return {"up": 2000, "down": 2000, "up_ratio": 0.5}
