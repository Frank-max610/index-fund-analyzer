#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数基金量化辅助系统 — 云端主流程
定稿规范 v1.0：每日10元定投 + PE/PB复合温度 + 指数温度切换策略

执行流程：数据采集 → 温度计算 → 决策 → 日报生成 → 数据持久化 → 推送
"""

import sys
import json
import os
import re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from curl_cffi import requests as curl_req

from config import (
    BASE_AMOUNT, WATCH_INDICES, THRESHOLDS, TEMPERATURE_CONFIG,
    DATA_DIR, DAILY_DIR, REPORTS_DIR, INDEX_SERIES_DIR,
    LEDGER_FILE, PORTFOLIO_STATE_FILE, FEISHU_WEBHOOK_URL,
)
from temperature import compute_index_temperature, decide_daily_action
from data.fetcher import (
    fetch_index_pe_pb, index_daily, north_flow,
    bond_yield_10y, macro_data, market_stats,
)
from notification.feishu import send_feishu

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
}

# ═══════════════════════════ 东方财富指数代码映射 ═══════════════════════════
EASTMONEY_SECID = {
    "000922": "1.000922",   # 中证红利（H30269 红利低波 的K线代理）
    "000510": "1.000510",   # 中证A500
    "000300": "1.000300",   # 沪深300
    "000905": "1.000905",   # 中证500
}


# ═══════════════════════════ 数据采集 ═══════════════════════════

def fetch_index_kline(code: str, days: int = 1300) -> dict:
    """
    获取单个指数的日线K线数据（东方财富API）。

    Returns:
        {close, chg, ret_5d, ret_20d, closes: [...], dates: [...]}
    """
    secid = EASTMONEY_SECID.get(code, f"1.{code}")
    result = {
        "code": code, "close": None, "chg": None,
        "ret_5d": None, "ret_20d": None, "closes": [], "dates": [],
    }

    try:
        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
            f"fields2=f51,f52,f53,f54,f55,f56,f57&"
            f"klt=101&fqt=1&end=20500101&lmt={days}"
        )
        resp = curl_req.get(url, headers=HEADERS, impersonate="chrome", timeout=15)
        resp.raise_for_status()
        json_data = resp.json()
        data_block = json_data.get("data")
        if data_block is None:
            print(f"  [WARN] {code} (secid={secid}) API返回data=null，该代码可能不被东方财富支持")
            return result
        klines = data_block.get("klines", [])

        if len(klines) < 50:
            print(f"  [WARN] {code} K-line 数据不足（{len(klines)}条）")
            return result

        closes = []
        dates = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 3:
                dates.append(parts[0])
                closes.append(float(parts[2]))

        result["closes"] = closes
        result["dates"] = dates
        result["close"] = closes[-1]

        if len(closes) >= 2:
            result["chg"] = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2)
        if len(closes) >= 6:
            result["ret_5d"] = round((closes[-1] - closes[-6]) / closes[-6] * 100, 2)
        if len(closes) >= 21:
            result["ret_20d"] = round((closes[-1] - closes[-21]) / closes[-21] * 100, 2)

    except Exception as e:
        print(f"  [ERROR] fetch_index_kline({code}): {e}")

    return result


def fetch_all_klines() -> dict:
    """获取所有监控指数的K线快照（含代理指数）。
    H30269（红利低波）通过代理 000922（中证红利）获取K线数据，
    因为东方财富不直接支持 H30269 的自定义指数代码。"""
    results = {}

    # 需要获取K线的代码集合（去重，含代理）
    codes_to_fetch = set()
    for idx_cfg in WATCH_INDICES:
        lookup = idx_cfg.get("proxy_code", idx_cfg["code"])
        codes_to_fetch.add(lookup)
        # 如果原始代码与代理不同，且原始代码在东方财富中有映射，也获取
        code = idx_cfg["code"]
        if code != lookup and code in EASTMONEY_SECID:
            codes_to_fetch.add(code)

    for code in sorted(codes_to_fetch):
        results[code] = fetch_index_kline(code)

    return results


def fetch_all_pe_pb() -> dict:
    """获取所有监控指数的PE/PB数据（含代理映射）"""
    results = {}

    for idx_cfg in WATCH_INDICES:
        code = idx_cfg["code"]
        lookup = idx_cfg.get("proxy_code", code)
        name = idx_cfg["name"]

        try:
            pe_pb = fetch_index_pe_pb(lookup)
        except Exception as e:
            print(f"  [WARN] PE/PB fetch failed for {name}({lookup}): {e}")
            pe_pb = {"pe": None, "pb": None, "pe_series": [], "pb_series": []}

        pe_pb["_lookup_code"] = lookup
        pe_pb["_name"] = name
        results[code] = pe_pb

    return results


def fetch_reference_indicators() -> dict:
    """获取参考指标：国债收益率、宏观数据、市场统计、北向资金"""
    result = {}

    try:
        result["bond_10y"] = bond_yield_10y()
    except Exception:
        result["bond_10y"] = 2.80

    try:
        result["macro"] = macro_data()
    except Exception:
        result["macro"] = {"pmi": 50.0, "cpi": 2.0, "m2": 8.0}

    try:
        result["market_stats"] = market_stats()
    except Exception:
        result["market_stats"] = {"up_ratio": 0.5}

    try:
        nf = north_flow(30)
        if not nf.empty and "net_flow" in nf.columns:
            result["north_flow_5d"] = round(float(nf["net_flow"].tail(5).sum() / 100), 1)
        else:
            result["north_flow_5d"] = 0
    except Exception:
        result["north_flow_5d"] = 0

    return result


# ═══════════════════════════ 温度计算 ═══════════════════════════

def compute_all_temperatures(kline_data: dict, pe_pb_data: dict) -> dict:
    """
    为所有监控指数计算复合温度。
    - 优先使用 PE/PB 复合温度
    - PE/PB 数据不足时回退为价格分位温度
    """
    results = {}

    for idx_cfg in WATCH_INDICES:
        code = idx_cfg["code"]
        name = idx_cfg["name"]
        lookup = idx_cfg.get("proxy_code", code)

        pe_pb = pe_pb_data.get(code, {})
        kl = kline_data.get(lookup, {}) or kline_data.get(code, {})

        pe_series = np.array(pe_pb.get("pe_series", []))
        pb_series = np.array(pe_pb.get("pb_series", []))
        current_pe = pe_pb.get("pe")
        current_pb = pe_pb.get("pb")

        # 尝试PE/PB复合温度
        temp_result = compute_index_temperature(
            pe_series=pe_series,
            pb_series=pb_series,
            current_pe=current_pe,
            current_pb=current_pb,
        )

        # PE/PB数据不足 → 回退价格分位温度
        if temp_result["status"] == "insufficient_data":
            closes = kl.get("closes", [])
            current_close = kl.get("close")
            if closes and current_close and len(closes) >= 60:
                price_temp = sum(1 for c in closes if c < current_close) / len(closes) * 100
                temp_result["composite_temperature"] = round(float(price_temp), 1)
                temp_result["pe_temperature"] = None
                temp_result["pb_temperature"] = None
                temp_result["status"] = "price_only"
                temp_result["data_points"] = len(closes)

        temp_result["index_name"] = name
        temp_result["index_code"] = code
        temp_result["lookup_code"] = lookup
        results[code] = temp_result

    return results


# ═══════════════════════════ 数据持久化 ═══════════════════════════

def ensure_dirs():
    """创建数据目录"""
    for d in [DATA_DIR, DAILY_DIR, REPORTS_DIR, INDEX_SERIES_DIR]:
        os.makedirs(d, exist_ok=True)


def load_json(filepath: str, default=None):
    """安全加载JSON文件"""
    if default is None:
        default = {}
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [WARN] 无法加载 {filepath}: {e}")
    return default


def save_json(filepath: str, data):
    """安全保存JSON文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [SAVE] {filepath}")


def load_ledger() -> dict:
    """加载交易账本"""
    default = {
        "version": 1,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "base_currency": "CNY",
        "records": [],
        "cumulative": {
            "total_invested": 0.0,
            "total_shares": 0.0,
            "current_value": 0.0,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
        },
    }
    return load_json(LEDGER_FILE, default)


def save_ledger(ledger: dict):
    """保存交易账本"""
    save_json(LEDGER_FILE, ledger)


def update_ledger(ledger: dict, decision: dict, nav_data: dict) -> dict:
    """
    根据每日决策更新交易账本。
    仅在 action == "DCA_NORMAL" 且 amount > 0 时记录买入。
    使用当日收盘净值（近似值，用户可在手机端录入实际成交净值覆写）。
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # 检查今日是否已记录（避免重复）
    for record in ledger["records"]:
        if record.get("date") == today:
            print(f"  [LEDGER] 今日已记录，跳过")
            return ledger

    if decision["action"] != "DCA_PAUSE" and decision["amount"] > 0:
        primary_code = decision["primary_target"]
        fund_code = decision["primary_fund_code"] or ""

        # 获取对应净值
        nav = 1.0
        if primary_code in nav_data:
            nav = nav_data[primary_code].get("close", 1.0) or 1.0

        shares = decision["amount"] / nav if nav > 0 else 0

        record = {
            "date": today,
            "fund_code": fund_code,
            "index_code": primary_code,
            "action": "定投",
            "amount": decision["amount"],
            "nav_at_action": round(nav, 4),
            "shares_acquired": round(shares, 4),
            "temperature_at_action": decision.get("primary_temperature"),
            "reason": decision["action_label"],
        }
        ledger["records"].append(record)

        # 更新累计统计
        ledger["cumulative"]["total_invested"] = round(
            sum(r["amount"] for r in ledger["records"]), 2
        )
        ledger["cumulative"]["total_shares"] = round(
            sum(r.get("shares_acquired", 0) for r in ledger["records"]), 4
        )

        print(f"  [LEDGER] 记录: {today} {fund_code} +{decision['amount']}元 "
              f"@ NAV={nav:.4f} → {shares:.4f}份")

    return ledger


def update_portfolio_state(ledger: dict, nav_data: dict):
    """根据账本和当前净值更新持仓状态"""
    cumulative = ledger["cumulative"]
    total_shares = cumulative.get("total_shares", 0)
    total_invested = cumulative.get("total_invested", 0)

    # 获取当前主力标的净值
    current_nav = 1.0
    if ledger["records"]:
        last_fund = ledger["records"][-1].get("index_code", "H30269")
        if last_fund in nav_data:
            current_nav = nav_data[last_fund].get("close", 1.0) or 1.0

    current_value = round(total_shares * current_nav, 2)
    unrealized_pnl = round(current_value - total_invested, 2)
    unrealized_pnl_pct = round(
        (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0, 2
    )

    portfolio = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_invested": total_invested,
        "total_shares": total_shares,
        "current_nav": round(current_nav, 4),
        "current_value": current_value,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_pct": unrealized_pnl_pct,
        "positions": [],
    }

    # 按基金汇总持仓
    fund_positions = {}
    for r in ledger["records"]:
        fc = r.get("fund_code", "unknown")
        if fc not in fund_positions:
            fund_positions[fc] = {"shares": 0, "invested": 0}
        fund_positions[fc]["shares"] += r.get("shares_acquired", 0)
        fund_positions[fc]["invested"] += r["amount"]

    for fc, pos in fund_positions.items():
        # 查找基金名称
        fund_name = fc
        for idx_cfg in WATCH_INDICES:
            if idx_cfg.get("fund_code") == fc:
                fund_name = idx_cfg.get("fund_name", fc)
                break

        portfolio["positions"].append({
            "fund_code": fc,
            "fund_name": fund_name,
            "total_shares": round(pos["shares"], 4),
            "total_invested": round(pos["invested"], 2),
            "avg_cost": round(pos["invested"] / pos["shares"], 4) if pos["shares"] > 0 else 0,
        })

    save_json(PORTFOLIO_STATE_FILE, portfolio)
    return portfolio


# ═══════════════════════════ 日报生成 ═══════════════════════════

def generate_daily_record(
    date_str: str,
    temperatures: dict,
    decision: dict,
    kline_data: dict,
    pe_pb_data: dict,
    reference: dict,
) -> dict:
    """生成标准化的每日数据JSON"""
    record = {
        "date": date_str,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "indices": {},
        "decision": {
            "primary_target": decision["primary_target"],
            "primary_name": decision["primary_name"],
            "primary_fund_code": decision.get("primary_fund_code"),
            "action": decision["action"],
            "action_label": decision["action_label"],
            "amount": decision["amount"],
            "alerts": decision["alerts"],
        },
        "reference_indicators": {
            "bond_10y": reference.get("bond_10y"),
            "money_fund_rate_est": round(reference.get("bond_10y", 2.8) * 0.6, 2),
            "market_breadth": round(reference.get("market_stats", {}).get("up_ratio", 0.5) * 100, 0),
            "north_flow_5d": reference.get("north_flow_5d"),
            "pmi": reference.get("macro", {}).get("pmi"),
            "cpi": reference.get("macro", {}).get("cpi"),
            "m2": reference.get("macro", {}).get("m2"),
        },
    }

    for idx_cfg in WATCH_INDICES:
        code = idx_cfg["code"]
        lookup = idx_cfg.get("proxy_code", code)
        temp = temperatures.get(code, {})
        kl = kline_data.get(lookup, {}) or kline_data.get(code, {})
        pe_pb = pe_pb_data.get(code, {})

        signal_info = decision.get("all_signals", {}).get(code, {})

        record["indices"][code] = {
            "name": idx_cfg["name"],
            "role": idx_cfg["role"],
            "fund_code": idx_cfg.get("fund_code"),
            "fund_name": idx_cfg.get("fund_name"),
            "proxy_code": idx_cfg.get("proxy_code"),
            # 行情数据
            "close": kl.get("close"),
            "chg_pct": kl.get("chg"),
            "ret_5d": kl.get("ret_5d"),
            "ret_20d": kl.get("ret_20d"),
            # 估值数据
            "pe": pe_pb.get("pe"),
            "pb": pe_pb.get("pb"),
            "pe_median": pe_pb.get("pe_median"),
            # 温度数据
            "pe_temperature": temp.get("pe_temperature"),
            "pb_temperature": temp.get("pb_temperature"),
            "composite_temperature": temp.get("composite_temperature"),
            "temperature_status": temp.get("status"),
            # 信号
            "signal": signal_info.get("signal", ""),
            "signal_emoji": signal_info.get("emoji", "⚪"),
            # 数据来源标注
            "data_source": "legulegu_pe_pb" if temp.get("status") == "ok" else
                           "price_fallback" if temp.get("status") == "price_only" else
                           temp.get("status", "unknown"),
        }

    return record


def generate_daily_report(record: dict) -> str:
    """根据每日数据JSON生成Markdown格式日报"""
    decision = record["decision"]
    ref = record["reference_indicators"]

    L = []
    L.append(f"📊 指数基金定投日报 | {record['date']}")
    L.append("")

    # === 核心结论 ===
    L.append("## 🎯 核心结论")
    L.append("")
    emoji = "🟢" if decision["action"] == "DCA_NORMAL" else "🔴"
    L.append(f"{emoji} **{decision['action_label']}**")
    L.append(f"- 主力标的：**{decision['primary_name']}**")
    L.append(f"- 基金代码：`{decision.get('primary_fund_code', 'N/A')}`")
    L.append(f"- 操作方向：{'✅ 正常定投' if decision['amount'] > 0 else '⏸️ 暂停定投'}")
    L.append(f"- 参考金额：**{decision['amount']} 元**")
    L.append("")

    if decision.get("alerts"):
        L.append("### ⚠️ 特别提醒")
        for alert in decision["alerts"]:
            L.append(f"- {alert}")
        L.append("")

    # === 各指数详情 ===
    L.append("## 📈 各指数详情")
    L.append("")
    L.append("| 指数 | 温度 | 收盘 | 今日 | 近20日 | PE | PB | 信号 |")
    L.append("|------|------|------|------|--------|----|----|------|")

    for code, data in record["indices"].items():
        name = data["name"]
        temp = data.get("composite_temperature")
        temp_str = f"{temp:.0f}%" if temp is not None else "N/A"
        close = data.get("close", "N/A")
        chg = data.get("chg_pct")
        chg_str = f"{chg:+.2f}%" if chg is not None else "N/A"
        ret_20d = data.get("ret_20d")
        ret_str = f"{ret_20d:+.2f}%" if ret_20d is not None else "N/A"
        pe = data.get("pe")
        pe_str = f"{pe:.2f}" if pe else "N/A"
        pb = data.get("pb")
        pb_str = f"{pb:.2f}" if pb else "N/A"
        emoji = data.get("signal_emoji", "⚪")

        L.append(f"| {emoji} {name} | {temp_str} | {close} | {chg_str} | {ret_str} | {pe_str} | {pb_str} | {data.get('signal', '')} |")

    L.append("")

    # === 参考指标 ===
    L.append("## 🌐 参考指标")
    L.append("")
    L.append(f"- 10年国债收益率：{ref.get('bond_10y', 'N/A')}%")
    L.append(f"- 货基利率(估)：{ref.get('money_fund_rate_est', 'N/A')}%")
    L.append(f"- 市场上涨占比：{ref.get('market_breadth', 'N/A')}%")
    L.append(f"- 北向资金(5日)：{ref.get('north_flow_5d', 'N/A')}亿")
    L.append(f"- PMI：{ref.get('pmi', 'N/A')} | CPI：{ref.get('cpi', 'N/A')}% | M2：{ref.get('m2', 'N/A')}%")
    L.append("")

    # === 操作规则 ===
    L.append("## 📋 当前规则")
    L.append("")
    L.append(f"- 主力温度 < {THRESHOLDS['primary_dca']}% → 正常定投 {BASE_AMOUNT}元/日")
    L.append(f"- 主力温度 {THRESHOLDS['primary_dca']}%~{THRESHOLDS['primary_hold']}% → 持有+定投")
    L.append(f"- 主力温度 > {THRESHOLDS['primary_pause']}% → 暂停定投")
    L.append(f"- A500 温度 < {THRESHOLDS['a500_switch']}% → 切换主力至A500")
    L.append(f"- 沪深300 温度 < {THRESHOLDS['hs300_bottom']}% → 抄底观察")
    L.append("")
    L.append(f"> 🤖 云端Agent自动生成 | {record['generated_at']}")

    return "\n".join(L)


# ═══════════════════════════ 主流程 ═══════════════════════════

def run_analysis():
    """主分析流程：采集 → 计算 → 决策 → 持久化 → 推送"""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"  指数基金量化分析 | {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # --- 1. 数据采集 ---
    print("[1/6] 数据采集...")
    kline_data = fetch_all_klines()
    pe_pb_data = fetch_all_pe_pb()
    reference = fetch_reference_indicators()
    print(f"  K线: {len(kline_data)}个标的  PE/PB: {len(pe_pb_data)}个标的")

    # --- 2. 温度计算 ---
    print("[2/6] 温度计算...")
    temperatures = compute_all_temperatures(kline_data, pe_pb_data)
    for code, t in temperatures.items():
        nm = t.get("index_name", code)
        ct = t.get("composite_temperature")
        ct_str = f"{ct:.1f}%" if ct is not None else "N/A"
        print(f"  {nm}({code}): 复合温度={ct_str} [{t.get('status', '?')}] "
              f"PE={t.get('pe_temperature', '?')} PB={t.get('pb_temperature', '?')}")

    # --- 3. 决策 ---
    print("[3/6] 策略决策...")
    decision = decide_daily_action(temperatures)
    print(f"  主力: {decision['primary_name']} | {decision['action_label']} | "
          f"金额: {decision['amount']}元")

    # --- 4. 生成日报 ---
    print("[4/6] 生成日报...")
    daily_record = generate_daily_record(today_str, temperatures, decision,
                                          kline_data, pe_pb_data, reference)
    daily_report = generate_daily_report(daily_record)

    # --- 5. 数据持久化 ---
    print("[5/6] 数据持久化...")
    ensure_dirs()

    # 保存当日数据JSON
    daily_path = os.path.join(DAILY_DIR, f"{today_str}.json")
    save_json(daily_path, daily_record)

    # 更新账本 & 持仓状态
    ledger = load_ledger()
    ledger = update_ledger(ledger, decision, kline_data)
    save_ledger(ledger)
    portfolio = update_portfolio_state(ledger, kline_data)

    # 保存日报Markdown
    report_path = os.path.join(REPORTS_DIR, f"{today_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(daily_report)
    print(f"  [SAVE] {report_path}")

    # 打印日报到控制台
    print(f"\n{daily_report}")

    # --- 6. 推送通知 ---
    print("\n[6/6] 推送通知...")
    title = f"📊 定投日报 | {decision['action_label'].split('（')[0]}"
    send_feishu(daily_report, title=title)

    print(f"\n{'='*60}")
    print(f"  分析完成 | {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    return daily_record


def main():
    """入口：支持 --once 单次运行 或 定时循环运行"""
    if "--once" in sys.argv:
        run_analysis()
        return

    import schedule
    import time

    # 启动时立即运行一次
    run_analysis()

    # 每个工作日 UTC 00:00（BJT 08:00）运行
    schedule.every().day.at("00:00").do(run_analysis)
    print("[SCHEDULE] 定时任务已启动，每个工作日 UTC 00:00 (BJT 08:00) 执行")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
