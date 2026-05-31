# -*- coding: utf-8 -*-
"""决策融合器：汇总各 Agent 信号 → 最终操作建议"""
from datetime import datetime
from config import SCORE_WEIGHTS, DECISION_MAP


def merge(results: list[dict]) -> dict:
    """加权融合各Agent打分"""
    total = 0.0
    details = []
    used_weights = 0.0

    for r in results:
        w = SCORE_WEIGHTS.get(r["agent"], 0.10)
        total += r["score"] * w
        used_weights += w
        details.append(
            f"{r['emoji']} {r['agent']}({r['score']:+.1f}×{w:.0%})"
        )

    # 归一化
    if used_weights > 0:
        total = total / used_weights

    total = round(total, 1)

    # 映射决策
    decision = "❓ 未知"
    for threshold, label in DECISION_MAP:
        if total >= threshold:
            decision = label
            break

    return {
        "total_score": total,
        "decision": decision,
        "details": details,
        "agents": results,
        "timestamp": datetime.now().isoformat(),
    }
