#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
007466 定投日报 — 每天早上 8 点
"""
import sys, json, re, pandas as pd, numpy as np
from datetime import datetime, timedelta, date
from curl_cffi import requests as curl_req

from config import (MAIN_FUND, WATCH_INDICES, THRESHOLDS, BASE_AMOUNT, MULTIPLIER, FEISHU_WEBHOOK_URL)
from notification.feishu import send_feishu

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# 实际可用的指数代码（东方财富）
INDEX_MAP = {
    "000922": {"name": "中证红利", "memo": "007466 近似基准"},
    "000015": {"name": "红利指数", "memo": "红利策略参考"},
    "000510": {"name": "中证A500", "memo": "备选切换标的"},
    "000300": {"name": "沪深300", "memo": "抄底观察"},
}

# ═══════════════════════════ 数据获取 ═══════════════════════════

def fetch_index_data(code: str) -> dict:
    """获取单个指数的温度、价格、涨跌幅"""
    secid = f"1.{code}" if not code.startswith("0.") and not code.startswith("1.") else code
    if not secid.startswith("0.") and not secid.startswith("1."):
        secid = f"1.{code}"

    result = {"code": code, "temp": None, "close": None,
              "chg": None, "ret_5d": None, "ret_20d": None}

    try:
        url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
               f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
               f"fields2=f51,f52,f53,f54,f55,f56,f57&"
               f"klt=101&fqt=1&end=20500101&lmt=1300")
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        lines = resp.json().get("data", {}).get("klines", [])
        if len(lines) < 50:
            return result

        closes = [float(l.split(",")[2]) for l in lines]
        latest = closes[-1]
        temp = sum(1 for c in closes if c < latest) / len(closes) * 100

        result["close"] = latest
        result["temp"] = round(temp, 0)
        result["chg"] = round((closes[-1]-closes[-2])/closes[-2]*100, 2) if len(closes)>=2 else None
        result["ret_5d"] = round((closes[-1]-closes[-6])/closes[-6]*100, 2) if len(closes)>=6 else None
        result["ret_20d"] = round((closes[-1]-closes[-21])/closes[-21]*100, 2) if len(closes)>=21 else None
    except Exception:
        pass
    return result


def fetch_all_indices() -> dict:
    """获取所有监控指数的数据"""
    return {code: fetch_index_data(code) for code in INDEX_MAP}


def fetch_money_fund_rate() -> float:
    try:
        url = "https://hq.sinajs.cn/list=bond_10y"
        h = {**HEADERS, "Referer": "https://finance.sina.com.cn/"}
        r = curl_req.get(url, headers=h, impersonate="chrome", timeout=15)
        m = re.search(r'bond_10y="([^"]*)"', r.text)
        if m: return round(float(m.group(1).split(",")[1]) * 0.6, 2)
    except: pass
    return 1.80


def fetch_bond_10y() -> float:
    try:
        url = "https://hq.sinajs.cn/list=bond_10y"
        h = {**HEADERS, "Referer": "https://finance.sina.com.cn/"}
        r = curl_req.get(url, headers=h, impersonate="chrome", timeout=15)
        m = re.search(r'bond_10y="([^"]*)"', r.text)
        if m: return float(m.group(1).split(",")[1])
    except: pass
    return 2.80


def fetch_market_breadth() -> float:
    try:
        url = ("https://push2.eastmoney.com/api/qt/clist/get?"
               "pn=1&pz=100&po=1&np=1&fltt=2&invt=2&"
               "fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f3")
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        diffs = resp.json().get("data", {}).get("diff", [])
        up = sum(1 for d in diffs if d.get("f3") and float(d["f3"]) > 0)
        return round(up/len(diffs)*100, 0) if diffs else 50
    except: pass
    return 50

# ═══════════════════════════ 决策 ═══════════════════════════

def decide_007466(d: dict, money_rate: float) -> dict:
    """针对 007466（中证红利基准）的操作建议"""
    temp = d.get("temp")
    reasons = []
    action = "normal"
    multiplier = MULTIPLIER["normal"]

    if temp is not None:
        if temp >= THRESHOLDS["red_dividend_sell"]:
            action, multiplier = "sell", MULTIPLIER["sell"]
            reasons.append(f"温度={temp:.0f}%，超过止盈线{THRESHOLDS['red_dividend_sell']}%，建议分批卖出")
        elif temp >= THRESHOLDS["red_dividend_pause"]:
            action, multiplier = "pause", MULTIPLIER["pause"]
            reasons.append(f"温度={temp:.0f}%，超过暂停线{THRESHOLDS['red_dividend_pause']}%，估值偏高，暂不加仓")
        elif temp < 20:
            action, multiplier = "strong_buy", MULTIPLIER["strong_buy"]
            reasons.append(f"温度仅{temp:.0f}%，极度低估，建议3倍买入")
        elif temp < THRESHOLDS["red_dividend_buy"]:
            if temp < 30:
                action, multiplier = "buy", MULTIPLIER["buy"]
                reasons.append(f"温度={temp:.0f}%，明显低估，建议2倍定投")
            else:
                action, multiplier = "normal", MULTIPLIER["normal"]
                reasons.append(f"温度={temp:.0f}%，在定投区间，正常买入")
        else:
            reasons.append(f"温度={temp:.0f}%，正常区间，按计划定投")
    else:
        reasons.append("数据缺失，按正常定投处理")

    if money_rate < THRESHOLDS["money_fund_rate"] and multiplier > 0:
        multiplier *= 1.5
        reasons.append(f"货基利率{money_rate}%低于{THRESHOLDS['money_fund_rate']}%，加码50%")

    amount = round(BASE_AMOUNT * multiplier) if multiplier > 0 else 0
    return {"action": action, "amount": amount, "multiplier": multiplier, "reasons": reasons}


def build_report(data: dict, decision: dict, money_rate: float,
                 bond_10y: float, breadth: float) -> str:
    now = datetime.now()
    d_zzhl = data["000922"]  # 中证红利 — 007466 基准
    d_hlzs = data["000015"]  # 红利指数
    d_a500 = data["000510"]
    d_hs300 = data["000300"]

    act = ACTION_LABEL.get(decision["action"], decision["action"])

    L = []
    L.append(f"007466 定投日报 | {now.strftime('%Y-%m-%d %A')}")
    L.append("")

    # ---- 核心结论 ----
    L.append(f"=== 核心结论 ===")
    L.append(f"007466（中证红利低波）→ {act}")
    if decision["amount"] > 0:
        L.append(f"建议投入：{decision['amount']} 元")
    elif decision["action"] == "sell":
        L.append("操作：减仓止盈")
    else:
        L.append("操作：暂不投入")
    L.append("")

    for r in decision["reasons"]:
        L.append(f"  {r}")
    L.append("")

    # ---- 各指数详情 ----
    L.append(f"=== 各指数详情 ===")
    for code, info in INDEX_MAP.items():
        d = data[code]
        name = info["name"]
        memo = info["memo"]
        temp = d.get("temp")
        close = d.get("close")
        chg = d.get("chg")
        ret_20d = d.get("ret_20d")

        if temp is not None:
            flag = "🟢" if temp < 50 else "🟡" if temp < 80 else "🔴"
            L.append(f"{flag} {name}（{code}）{memo}")
            L.append(f"   温度={temp:.0f}%  收盘={close}  今日{chg:+.2f}%  近20日{ret_20d:+.2f}%")
        else:
            L.append(f"   {name}（{code}）数据缺失")
    L.append("")

    # ---- 参考指标 ----
    L.append(f"=== 参考指标 ===")
    L.append(f"  货基利率(估)：{money_rate}%（加码线 {THRESHOLDS['money_fund_rate']}%）")
    L.append(f"  10年国债：{bond_10y}%  市场上涨占比：{breadth:.0f}%")
    L.append("")

    # ---- 切换判断 ----
    a5_temp = d_a500.get("temp")
    h3_temp = d_hs300.get("temp")
    if a5_temp is not None and a5_temp < THRESHOLDS["a500_switch"]:
        L.append(f"  → A500温度{a5_temp:.0f}%低于切换线{THRESHOLDS['a500_switch']}%，可以从红利低波切部分到A500")
    if h3_temp is not None and h3_temp < THRESHOLDS["hs300_bottom"]:
        L.append(f"  → 沪深300温度{h3_temp:.0f}%低于抄底线{THRESHOLDS['hs300_bottom']}%，可以分配部分资金抄底")
    L.append("")

    # ---- 阈值 ----
    L.append(f"=== 操作规则 ===")
    L.append(f"  温度 < {THRESHOLDS['red_dividend_buy']}% → 买入")
    L.append(f"  温度 {THRESHOLDS['red_dividend_buy']}-{THRESHOLDS['red_dividend_pause']}% → 正常")
    L.append(f"  温度 > {THRESHOLDS['red_dividend_pause']}% → 暂停")
    L.append(f"  温度 > {THRESHOLDS['red_dividend_sell']}% → 卖出")

    return "\n".join(L)


ACTION_LABEL = {
    "strong_buy": "加倍买入", "buy": "加大定投", "normal": "正常定投",
    "reduce": "减半定投", "pause": "暂停定投", "sell": "考虑止盈",
}

# ═══════════════════════════ 主流程 ═══════════════════════════

def run_analysis():
    now = datetime.now()
    print(f"=== 007466 定投分析 {now.strftime('%Y-%m-%d %H:%M:%S')} ===")

    data = fetch_all_indices()
    money_rate = fetch_money_fund_rate()
    bond_10y = fetch_bond_10y()
    breadth = fetch_market_breadth()

    # 打印摘要
    for code, info in INDEX_MAP.items():
        d = data[code]
        print(f"  {info['name']}({code}) T={d.get('temp','?')}% close={d.get('close','?')} chg={d.get('chg','?')}%")
    print(f"  货基={money_rate}% 国债={bond_10y}% 涨比={breadth}%")

    # 007466 决策（用 000922 中证红利作为基准）
    decision = decide_007466(data["000922"], money_rate)
    print(f"  007466: {ACTION_LABEL[decision['action']]} 金额={decision['amount']}元")

    report = build_report(data, decision, money_rate, bond_10y, breadth)
    print()
    print(report)

    send_feishu(report, title=f"007466 定投 | {ACTION_LABEL[decision['action']]}")
    print(f"完成 {datetime.now().strftime('%H:%M:%S')}")


def main():
    if "--once" in sys.argv:
        run_analysis()
        return
    import schedule, time
    schedule.every().day.at("00:00").do(run_analysis)
    run_analysis()
    while True: schedule.run_pending(); time.sleep(60)

if __name__ == "__main__":
    main()
