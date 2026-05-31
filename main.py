#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数基金定投辅助器 — 主入口
用法：
  python main.py --once    手动运行一次分析
  python main.py           常驻后台，每个交易日 15:30 自动运行
"""
import sys
import time
import schedule
from datetime import datetime

from config import TRACKED_INDICES
from agents.valuation import ValuationAgent
from agents.technical import TechnicalAgent
from agents.macro import MacroAgent
from agents.fund_flow import FundFlowAgent
from agents.sentiment import SentimentAgent
from agents.risk import RiskAgent
from agents.fundamentals import FundamentalsAgent
from agents.decider import merge
from notification.report import simple_report
from notification.feishu import send_feishu


def is_trading_day() -> bool:
    """判断是否交易日（简化：周一到周五）"""
    return datetime.now().weekday() < 5


def run_analysis():
    """执行一次完整分析"""
    print(f"\n{'='*50}")
    print(f"🔄 开始分析 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    # 初始化 Agent Team
    agents = [
        ValuationAgent(),
        TechnicalAgent(),
        MacroAgent(),
        FundFlowAgent(),
        SentimentAgent(),
        RiskAgent(),
        FundamentalsAgent(),
    ]

    all_results = []

    for code, name, etf in TRACKED_INDICES:
        print(f"\n--- 分析 {name} ({code}) ---")
        try:
            agent_results = []
            for agent in agents:
                try:
                    result = agent.run(code)
                    agent_results.append(result)
                    print(f"  {result['emoji']} {result['agent']}: "
                          f"{result['score']:+.1f} | {result['detail'][:60]}")
                except Exception as e:
                    print(f"  ❌ {agent.name}: {e}")
                    agent_results.append({
                        "agent": agent.name,
                        "emoji": agent.emoji,
                        "score": 0,
                        "detail": f"错误: {e}",
                        "indicators": {"score": 0},
                    })
            merged = merge(agent_results)
            all_results.append({
                "code": code, "name": name, "etf": etf,
                "merge": merged,
            })
            print(f"  → 综合: {merged['total_score']:+.1f} {merged['decision']}")
        except Exception as e:
            print(f"  ❌ {name} 分析失败: {e}")

    if not all_results:
        print("❌ 无有效分析结果")
        return

    # 生成并推送日报
    report = simple_report(all_results)
    print(f"\n{'='*50}")
    print(report)
    print(f"{'='*50}")

    send_feishu(report, title="指数基金定投日报")

    print(f"\n✅ 分析完成 {datetime.now().strftime('%H:%M:%S')}")


def main():
    if "--once" in sys.argv:
        run_analysis()
        return

    print("📊 指数基金定投辅助器 已启动")
    print(f"⏰ 每个交易日 15:30 自动分析")
    print(f"📡 飞书推送: {'已配置' if __import__('config').FEISHU_WEBHOOK_URL else '❌ 未配置'}")
    print()

    # 立即运行一次
    if is_trading_day():
        run_analysis()
    else:
        print("🏖 今天非交易日，等待下一个交易日...")

    # 定时调度
    schedule.every().day.at("15:30").do(
        lambda: run_analysis() if is_trading_day() else print("🏖 非交易日跳过")
    )

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
