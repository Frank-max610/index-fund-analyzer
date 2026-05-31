#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
007466 定投日报
每天早上跑一次，告诉你该买还是该卖、买多少。
"""
import sys
import json
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from curl_cffi import requests as curl_req

from config import (
    MAIN_FUND, WATCH_INDICES, THRESHOLDS, BASE_AMOUNT, MULTIPLIER,
    FEISHU_WEBHOOK_URL, DB_PATH,
)
from notification.feishu import send_feishu

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
}

# ══════════════════════════════════════════════
# 估值温度获取
# ══════════════════════════════════════════════

LEGU_SLUGS = {
    "H30269": "红利低波",
    "000510": "中证A500",
    "000300": "沪深300",
    "000922": "中证红利",
}

# 反查：名称 -> legulegu slug
NAME_TO_SLUG = {
    "红利低波": "红利低波",
    "中证A500": "中证A500",
    "沪深300": "hs300",
    "中证红利": "zz500",
}


def fetch_valuation_percentile(name: str) -> dict:
    """获取指数估值温度（PE分位）"""
    slug = NAME_TO_SLUG.get(name, "hs300")

    result = {
        "name": name, "pe": None, "pb": None,
        "pe_pct": None, "pb_pct": None,
        "date": None, "source": "",
    }

    # 尝试 legulegu
    for kind, endpoint in [("pe", "ttm-lyr"), ("pb", "pb")]:
        try:
            url = f"https://legulegu.com/stockdata/{slug}-{endpoint}"
            resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
            if resp.status_code != 200:
                continue

            html = resp.text
            # 尝试解析 data JSON
            m = re.search(r'data\s*:\s*(\[.*?\])', html, re.DOTALL)
            if m:
                records = json.loads(m.group(1))
                if records:
                    vals = []
                    for r in records:
                        for k, v in r.items():
                            if k in ("close", "value") or kind in k.lower():
                                try:
                                    vals.append(float(v))
                                except (ValueError, TypeError):
                                    pass
                    if vals:
                        latest = vals[-1]
                        pct = sum(1 for v in vals if v < latest) / len(vals)
                        if kind == "pe":
                            result["pe"] = round(latest, 2)
                            result["pe_pct"] = round(pct * 100, 0)
                        else:
                            result["pb"] = round(latest, 2)
                            result["pb_pct"] = round(pct * 100, 0)
            result["source"] = "legulegu"
        except Exception:
            pass

    return result


def fetch_index_price(code: str, name: str) -> dict:
    """获取指数最近价格和涨跌幅"""
    # 东方财富 K 线
    market_map = {
        "H30269": "1.H30269", "000510": "1.000510",
        "000300": "1.000300", "000922": "1.000922",
        "399006": "0.399006", "000016": "1.000016",
    }
    secid = market_map.get(code, f"1.{code}")

    try:
        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
            f"fields2=f51,f52,f53,f54,f55,f56,f57&"
            f"klt=101&fqt=1&end=20500101&lmt=60"
        )
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        data = resp.json()
        if data.get("data") and data["data"].get("klines"):
            lines = data["data"]["klines"]
            if len(lines) >= 2:
                latest = lines[-1].split(",")
                prev = lines[-2].split(",")
                close = float(latest[2])
                prev_close = float(prev[2])
                chg_pct = round((close - prev_close) / prev_close * 100, 2)

                # 5日、20日涨跌
                if len(lines) >= 6:
                    close_5d = float(lines[-6].split(",")[2])
                    ret_5d = round((close - close_5d) / close_5d * 100, 2)
                else:
                    ret_5d = None

                if len(lines) >= 21:
                    close_20d = float(lines[-21].split(",")[2])
                    ret_20d = round((close - close_20d) / close_20d * 100, 2)
                else:
                    ret_20d = None

                return {
                    "close": close, "chg_pct": chg_pct,
                    "ret_5d": ret_5d, "ret_20d": ret_20d,
                }
    except Exception:
        pass

    return {"close": None, "chg_pct": None, "ret_5d": None, "ret_20d": None}


def fetch_money_fund_rate() -> float:
    """获取余额宝/零钱通利率（用 10 年国债收益率的 60% 近似）"""
    try:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "sortColumns=TRADE_DATE&sortTypes=-1&pageSize=3&pageNumber=1&"
            "reportName=RPT_ECONOMY_BOND&columns=ALL&"
            "filter=(TRADE_DATE>='2024-01-01')"
        )
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        d = resp.json()
        if d.get("result") and d["result"].get("data"):
            for row in d["result"]["data"]:
                for k in ["BOND_YIELD_10Y", "CLOSE_YIELD_10Y"]:
                    if k in row and row[k]:
                        return round(float(row[k]) * 0.6, 2)
    except Exception:
        pass
    return 1.80  # 默认


def fetch_market_sentiment() -> dict:
    """全市场涨跌统计"""
    try:
        url = (
            "https://push2.eastmoney.com/api/qt/clist/get?"
            "pn=1&pz=50&po=1&np=1&fltt=2&invt=2&"
            "fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&"
            "fields=f2,f3"
        )
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        d = resp.json()
        if d.get("data") and d["data"].get("diff"):
            up = down = 0
            for item in d["data"]["diff"]:
                pct = item.get("f3")
                if pct is None:
                    continue
                pct = float(pct)
                if pct > 0:
                    up += 1
                elif pct < 0:
                    down += 1
            t = up + down
            return {"up_pct": round(up / t * 100, 0) if t > 0 else 50}
    except Exception:
        pass
    return {"up_pct": 50}


def fetch_bond_10y() -> float:
    """10 年期国债收益率"""
    try:
        url = "https://hq.sinajs.cn/list=bond_10y"
        h = {**HEADERS, "Referer": "https://finance.sina.com.cn/"}
        r = curl_req.get(url, headers=h, impersonate="chrome", timeout=15)
        m = re.search(r'bond_10y="([^"]*)"', r.text)
        if m:
            parts = m.group(1).split(",")
            if len(parts) >= 2:
                return float(parts[1])
    except Exception:
        pass
    return 2.80


# ══════════════════════════════════════════════
# 决策引擎
# ══════════════════════════════════════════════

def decide(val: dict, price: dict, money_rate: float,
           a500_val: dict, hs300_val: dict) -> dict:
    """根据阈值生成操作建议"""
    pe_pct = val.get("pe_pct")
    pe = val.get("pe")
    pb_pct = val.get("pb_pct")
    name = val.get("name", "红利低波")

    # 默认
    action = "hold"
    multiplier = MULTIPLIER["normal"]
    reason_parts = []

    if pe_pct is not None:
        # 温度判断
        if pe_pct >= THRESHOLDS["red_dividend_sell"]:
            action = "sell"
            multiplier = MULTIPLIER["sell"]
            reason_parts.append(
                f"PE温度={pe_pct:.0f}%，超过{THRESHOLDS['red_dividend_sell']}%止盈线"
            )
        elif pe_pct >= THRESHOLDS["red_dividend_pause"]:
            action = "pause"
            multiplier = MULTIPLIER["pause"]
            reason_parts.append(
                f"PE温度={pe_pct:.0f}%，超过{THRESHOLDS['red_dividend_pause']}%暂停线"
            )
        elif pe_pct < THRESHOLDS["red_dividend_buy"]:
            # 低估区域：温度越低买越多
            if pe_pct < 20:
                action = "strong_buy"
                multiplier = MULTIPLIER["strong_buy"]
                reason_parts.append(
                    f"PE温度仅{pe_pct:.0f}%，极度低估，建议加倍买入"
                )
            elif pe_pct < 35:
                action = "buy"
                multiplier = MULTIPLIER["buy"]
                reason_parts.append(
                    f"PE温度={pe_pct:.0f}%，低于{THRESHOLDS['red_dividend_buy']}%定投线，加倍定投"
                )
            else:
                action = "normal"
                multiplier = MULTIPLIER["normal"]
                reason_parts.append(
                    f"PE温度={pe_pct:.0f}%，在定投区间，正常买入"
                )
        else:
            reason_parts.append(
                f"PE温度={pe_pct:.0f}%，在{THRESHOLDS['red_dividend_buy']}%-{THRESHOLDS['red_dividend_pause']}%之间，正常定投"
            )
    else:
        reason_parts.append("PE数据缺失，按正常定投处理")

    # 余额宝利率判断
    if money_rate < THRESHOLDS["money_fund_rate"]:
        if multiplier > 0:
            multiplier *= 1.5  # 利率低，加码 50%
            reason_parts.append(
                f"货基利率={money_rate}%，低于{THRESHOLDS['money_fund_rate']}%，钱放着贬值，加大投入"
            )

    # A500 切换判断
    if a500_val.get("pe_pct") is not None and a500_val["pe_pct"] < THRESHOLDS["a500_switch"]:
        reason_parts.append(
            f"A500温度={a500_val['pe_pct']:.0f}%，低于{THRESHOLDS['a500_switch']}%，"
            f"可以考虑从红利低波切一部分到A500"
        )

    # 沪深300 抄底判断
    if hs300_val.get("pe_pct") is not None and hs300_val["pe_pct"] < THRESHOLDS["hs300_bottom"]:
        reason_parts.append(
            f"沪深300温度={hs300_val['pe_pct']:.0f}%，低于{THRESHOLDS['hs300_bottom']}%抄底线，"
            f"可以分部分资金抄底"
        )

    amount = round(BASE_AMOUNT * multiplier) if multiplier > 0 else 0

    return {
        "action": action,
        "amount": amount,
        "multiplier": multiplier,
        "reasons": reason_parts,
        "pe_pct": pe_pct,
        "pe": pe,
        "pb_pct": pb_pct,
        "pb": val.get("pb"),
    }


# ══════════════════════════════════════════════
# 日报生成
# ══════════════════════════════════════════════

ACTION_LABEL = {
    "strong_buy": "加倍买入",
    "buy": "加大定投",
    "normal": "正常定投",
    "hold": "正常定投",
    "reduce": "减半定投",
    "pause": "暂停定投",
    "sell": "考虑止盈",
}


def build_report(decision: dict, val: dict, price: dict,
                 money_rate: float, bond_10y: float,
                 market: dict, a500_v: dict, hs300_v: dict) -> str:
    """生成纯文字日报"""
    now = datetime.now()
    lines = []
    lines.append(f"007466 定投日报 | {now.strftime('%Y-%m-%d %A')}")
    lines.append("")

    # 核心结论
    action = decision["action"]
    amount = decision["amount"]
    label = ACTION_LABEL.get(action, action)
    lines.append(f"今日操作：{label}")
    if amount > 0:
        lines.append(f"建议投入：{amount} 元")
    elif action == "sell":
        lines.append("建议：考虑减仓止盈")
    lines.append("")

    # 决策理由
    lines.append("决策依据：")
    for r in decision["reasons"]:
        lines.append(f"  - {r}")
    lines.append("")

    # 关键数据
    lines.append("今日数据：")
    if decision["pe"] is not None:
        lines.append(f"  007466 估值温度：{decision['pe_pct']:.0f}%（PE={decision['pe']:.2f}）")
    if decision.get("pb_pct") is not None:
        lines.append(f"  PB 温度：{decision['pb_pct']:.0f}%（PB={decision['pb']:.2f}）")
    if price.get("close") is not None:
        lines.append(f"  红利低波指数：{price['close']:.2f}，今日 {price['chg_pct']:+.2f}%")
        if price.get("ret_5d") is not None:
            lines.append(f"  近5日：{price['ret_5d']:+.2f}%  近20日：{price['ret_20d']:+.2f}%")
    lines.append("")

    # 参考指标
    lines.append("参考指标：")
    if a500_v.get("pe_pct") is not None:
        lines.append(f"  A500 温度：{a500_v['pe_pct']:.0f}%（切换线 {THRESHOLDS['a500_switch']}%）")
    if hs300_v.get("pe_pct") is not None:
        lines.append(f"  沪深300 温度：{hs300_v['pe_pct']:.0f}%（抄底线 {THRESHOLDS['hs300_bottom']}%）")
    lines.append(f"  货基利率(估)：{money_rate}%（加码线 {THRESHOLDS['money_fund_rate']}%）")
    lines.append(f"  10年国债：{bond_10y}%")
    lines.append(f"  全市场上涨占比：{market.get('up_pct', 50):.0f}%")
    lines.append("")

    # 阈值速查
    lines.append("操作阈值：")
    lines.append(f"  温度 < {THRESHOLDS['red_dividend_buy']}% → 定投买入")
    lines.append(f"  温度 {THRESHOLDS['red_dividend_buy']}-{THRESHOLDS['red_dividend_pause']}% → 正常定投")
    lines.append(f"  温度 > {THRESHOLDS['red_dividend_pause']}% → 暂停")
    lines.append(f"  温度 > {THRESHOLDS['red_dividend_sell']}% → 止盈卖出")

    return "\n".join(lines)


# ══════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════

def run_analysis():
    print(f"开始分析 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 获取估值温度
    print("  获取估值数据...")
    val = fetch_valuation_percentile("红利低波")
    a500_val = fetch_valuation_percentile("中证A500")
    hs300_val = fetch_valuation_percentile("沪深300")
    print(f"  红利低波 PE温度={val.get('pe_pct','?')}%  "
          f"A500={a500_val.get('pe_pct','?')}%  "
          f"沪深300={hs300_val.get('pe_pct','?')}%")

    # 2. 指数价格
    print("  获取价格数据...")
    price = fetch_index_price("H30269", "红利低波")
    print(f"  红利低波指数: close={price.get('close','?')}  chg={price.get('chg_pct','?')}%")

    # 3. 宏观参考
    print("  获取宏观数据...")
    money_rate = fetch_money_fund_rate()
    bond_10y = fetch_bond_10y()
    market = fetch_market_sentiment()
    print(f"  货基利率={money_rate}%  国债={bond_10y}%  上涨占比={market.get('up_pct','?')}%")

    # 4. 决策
    decision = decide(val, price, money_rate, a500_val, hs300_val)
    action = decision["action"]
    label = ACTION_LABEL.get(action, action)
    print(f"  决策: {label}  金额: {decision['amount']}元")

    # 5. 生成日报
    report = build_report(decision, val, price, money_rate, bond_10y, market,
                          a500_val, hs300_val)
    print()
    print(report)
    print()

    # 6. 飞书推送
    send_feishu(report, title=f"007466 定投日报 | {label}")

    print(f"完成 {datetime.now().strftime('%H:%M:%S')}")


def main():
    if "--once" in sys.argv:
        run_analysis()
        return

    import schedule
    import time

    # 每天早上 8:00
    schedule.every().day.at("00:00").do(run_analysis)  # UTC 00:00 = 北京 8:00

    # 启动立即跑一次
    run_analysis()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
