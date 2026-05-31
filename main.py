#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
007466 定投日报 — 每天早上跑一次
"""
import sys, json, re, pandas as pd, numpy as np
from datetime import datetime, timedelta, date
from curl_cffi import requests as curl_req

from config import (MAIN_FUND, WATCH_INDICES, THRESHOLDS, BASE_AMOUNT, MULTIPLIER, FEISHU_WEBHOOK_URL)
from notification.feishu import send_feishu

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ══════════════════════════════════ 数据获取 ══════════════════════════════════

def fetch_temperature(code: str, name: str) -> dict:
    """价格分位温度：当前价在近5年价格区间中的百分位。越高越贵。"""
    market_map = {
        "H30269": "1.H30269", "000510": "1.000510",
        "000300": "1.000300", "000922": "1.000922",
        "399006": "0.399006", "000016": "1.000016",
    }
    secid = market_map.get(code, f"1.{code}")
    result = {"name": name, "temp": None, "close": None,
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
        # 温度 = 当前价在全部价中的分位
        temp = sum(1 for c in closes if c < latest) / len(closes) * 100

        result.update({"close": latest, "temp": round(temp, 0)})
        result["chg"] = round((closes[-1]-closes[-2])/closes[-2]*100, 2) if len(closes)>=2 else None
        result["ret_5d"] = round((closes[-1]-closes[-6])/closes[-6]*100, 2) if len(closes)>=6 else None
        result["ret_20d"] = round((closes[-1]-closes[-21])/closes[-21]*100, 2) if len(closes)>=21 else None
    except Exception:
        pass
    return result


def fetch_money_fund_rate() -> float:
    """货基收益率（10年国债 × 0.6 近似）"""
    try:
        url = ("https://hq.sinajs.cn/list=bond_10y")
        h = {**HEADERS, "Referer": "https://finance.sina.com.cn/"}
        r = curl_req.get(url, headers=h, impersonate="chrome", timeout=15)
        m = re.search(r'bond_10y="([^"]*)"', r.text)
        if m: return round(float(m.group(1).split(",")[1]) * 0.6, 2)
    except Exception: pass
    return 1.80


def fetch_bond_10y() -> float:
    """10年期国债收益率"""
    try:
        url = "https://hq.sinajs.cn/list=bond_10y"
        h = {**HEADERS, "Referer": "https://finance.sina.com.cn/"}
        r = curl_req.get(url, headers=h, impersonate="chrome", timeout=15)
        m = re.search(r'bond_10y="([^"]*)"', r.text)
        if m: return float(m.group(1).split(",")[1])
    except Exception: pass
    return 2.80


def fetch_market_breadth() -> float:
    """全市场上涨占比"""
    try:
        url = ("https://push2.eastmoney.com/api/qt/clist/get?"
               "pn=1&pz=100&po=1&np=1&fltt=2&invt=2&"
               "fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f3")
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        diffs = resp.json().get("data", {}).get("diff", [])
        up = sum(1 for d in diffs if d.get("f3") and float(d["f3"]) > 0)
        total = len(diffs)
        return round(up/total*100, 0) if total > 0 else 50
    except Exception: pass
    return 50

# ══════════════════════════════════ 决策引擎 ══════════════════════════════════

ACTION_LABEL = {
    "strong_buy": "加倍买入", "buy": "加大定投", "normal": "正常定投",
    "reduce": "减半定投", "pause": "暂停定投", "sell": "考虑止盈",
}


def decide(main_data: dict, a500_data: dict, hs300_data: dict,
           money_rate: float) -> dict:
    """根据温度阈值生成操作建议"""
    temp = main_data.get("temp")

    reasons = []
    action = "normal"
    multiplier = MULTIPLIER["normal"]

    if temp is not None:
        if temp >= THRESHOLDS["red_dividend_sell"]:
            action, multiplier = "sell", MULTIPLIER["sell"]
            reasons.append(f"温度={temp:.0f}%，超过{THRESHOLDS['red_dividend_sell']}%止盈线，建议减仓")
        elif temp >= THRESHOLDS["red_dividend_pause"]:
            action, multiplier = "pause", MULTIPLIER["pause"]
            reasons.append(f"温度={temp:.0f}%，超过{THRESHOLDS['red_dividend_pause']}%暂停线，暂不加仓")
        elif temp < 20:
            action, multiplier = "strong_buy", MULTIPLIER["strong_buy"]
            reasons.append(f"温度仅{temp:.0f}%，极度低估，加倍买入")
        elif temp < 35:
            action, multiplier = "buy", MULTIPLIER["buy"]
            reasons.append(f"温度={temp:.0f}%，低于定投线，加大买入")
        elif temp < THRESHOLDS["red_dividend_buy"]:
            action, multiplier = "normal", MULTIPLIER["normal"]
            reasons.append(f"温度={temp:.0f}%，在定投区间，正常买入")
        else:
            reasons.append(f"温度={temp:.0f}%，在{THRESHOLDS['red_dividend_buy']}-{THRESHOLDS['red_dividend_pause']}%之间，正常定投")
    else:
        reasons.append("温度数据缺失，按正常定投处理")

    # 余额宝利率加码
    if money_rate < THRESHOLDS["money_fund_rate"] and multiplier > 0:
        multiplier *= 1.5
        reasons.append(f"货基利率={money_rate}%，低于{THRESHOLDS['money_fund_rate']}%，钱贬值不如投，加码50%")

    # A500 切换
    a5_temp = a500_data.get("temp")
    if a5_temp is not None and a5_temp < THRESHOLDS["a500_switch"]:
        reasons.append(f"A500温度={a5_temp:.0f}%，低于切换线{THRESHOLDS['a500_switch']}%，可从红利低波切部分到A500")

    # 沪深300 抄底
    h3_temp = hs300_data.get("temp")
    if h3_temp is not None and h3_temp < THRESHOLDS["hs300_bottom"]:
        reasons.append(f"沪深300温度={h3_temp:.0f}%，低于抄底线{THRESHOLDS['hs300_bottom']}%，可分配部分资金抄底")

    amount = round(BASE_AMOUNT * multiplier) if multiplier > 0 else 0

    return {"action": action, "amount": amount, "multiplier": multiplier, "reasons": reasons}


# ══════════════════════════════════ 报告生成 ══════════════════════════════════

def build_report(decision: dict, main_d: dict, a500_d: dict, hs300_d: dict,
                 money_rate: float, bond_10y: float, breadth: float) -> str:
    now = datetime.now()
    lines = [
        f"007466 定投日报 | {now.strftime('%Y-%m-%d %A')}",
        "",
        f"今日操作：{ACTION_LABEL.get(decision['action'], decision['action'])}",
    ]
    if decision["amount"] > 0:
        lines.append(f"建议投入：{decision['amount']} 元")
    elif decision["action"] == "sell":
        lines.append("建议：减仓止盈，落袋为安")

    lines.append("")
    lines.append("决策依据：")
    for r in decision["reasons"]:
        lines.append(f"  - {r}")

    lines.append("")
    lines.append("今日数据：")
    if main_d.get("temp") is not None:
        lines.append(f"  007466(红利低波) 温度：{main_d['temp']:.0f}%  收盘：{main_d.get('close','?')}")
    if main_d.get("chg") is not None:
        lines.append(f"  今日涨跌：{main_d['chg']:+.2f}%  近5日：{main_d.get('ret_5d','?')}%  近20日：{main_d.get('ret_20d','?')}%")

    lines.append("")
    if a500_d.get("temp") is not None:
        lines.append(f"  A500 温度：{a500_d['temp']:.0f}%（切换线 {THRESHOLDS['a500_switch']}%）")
    if hs300_d.get("temp") is not None:
        lines.append(f"  沪深300 温度：{hs300_d['temp']:.0f}%（抄底线 {THRESHOLDS['hs300_bottom']}%）")
    lines.append(f"  货基利率(估)：{money_rate}%（加码线 {THRESHOLDS['money_fund_rate']}%）")
    lines.append(f"  10年国债：{bond_10y}%  上涨占比：{breadth:.0f}%")

    lines.append("")
    lines.append("阈值速查：")
    lines.append(f"  温度 < {THRESHOLDS['red_dividend_buy']}% → 定投买入")
    lines.append(f"  温度 {THRESHOLDS['red_dividend_buy']}-{THRESHOLDS['red_dividend_pause']}% → 正常定投")
    lines.append(f"  温度 > {THRESHOLDS['red_dividend_pause']}% → 暂停")
    lines.append(f"  温度 > {THRESHOLDS['red_dividend_sell']}% → 止盈卖出")

    return "\n".join(lines)


# ══════════════════════════════════ 主流程 ══════════════════════════════════

def run_analysis():
    now = datetime.now()
    print(f"开始分析 {now.strftime('%Y-%m-%d %H:%M:%S')}")

    print("  获取数据...")
    main_data = fetch_temperature("000922", "红利低波")  # 000922=中证红利≈红利低波
    a500_data = fetch_temperature("000510", "A500")
    hs300_data = fetch_temperature("000300", "沪深300")
    money_rate = fetch_money_fund_rate()
    bond_10y = fetch_bond_10y()
    breadth = fetch_market_breadth()

    print(f"  红利低波 T={main_data.get('temp','?')}%  close={main_data.get('close','?')}  chg={main_data.get('chg','?')}%")
    print(f"  A500 T={a500_data.get('temp','?')}%  沪深300 T={hs300_data.get('temp','?')}%")
    print(f"  货基={money_rate}%  国债={bond_10y}%  涨比={breadth}%")

    decision = decide(main_data, a500_data, hs300_data, money_rate)
    print(f"  决策: {ACTION_LABEL.get(decision['action'])}  金额: {decision['amount']}元")

    report = build_report(decision, main_data, a500_data, hs300_data,
                          money_rate, bond_10y, breadth)
    print()
    print(report)
    print()

    send_feishu(report, title=f"007466 定投 | {ACTION_LABEL.get(decision['action'], decision['action'])}")
    print(f"完成 {datetime.now().strftime('%H:%M:%S')}")


def main():
    if "--once" in sys.argv:
        run_analysis()
        return

    import schedule, time
    schedule.every().day.at("00:00").do(run_analysis)
    run_analysis()
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
