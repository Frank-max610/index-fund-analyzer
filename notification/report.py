# -*- coding: utf-8 -*-
"""日报模板生成"""
from datetime import datetime
from config import TRACKED_INDICES, SCORE_WEIGHTS


def _score_bar(score: float, width: int = 10) -> str:
    """可视化打分条"""
    pos = max(0, min(width, int((score + 3) / 6 * width)))
    bar = ""
    for i in range(width):
        if i < pos:
            bar += "█" if score > 0 else "░"
        else:
            bar += "░"
    return bar


def daily_report(all_index_results: list[dict]) -> str:
    """生成完整日报"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %A")

    lines = []
    lines.append(f"📊 **指数基金定投日报** | {date_str}")
    lines.append("━" * 28)
    lines.append("")

    for idx_result in all_index_results:
        name = idx_result["name"]
        code = idx_result["code"]
        merge = idx_result["merge"]

        total = merge["total_score"]
        decision = merge["decision"]
        bar = _score_bar(total)

        lines.append(f"## {name} ({code})")
        lines.append(f"🔍 综合评分：**{total:+.1f}** {bar} → {decision}")
        lines.append("")

        # 各Agent详情
        for agent_r in merge["agents"]:
            s = agent_r["score"]
            flag = "🟢" if s > 0 else "🔴" if s < 0 else "⚪"
            lines.append(
                f"{agent_r['emoji']} **{agent_r['agent']}**：{s:+.1f} {flag}"
            )
            lines.append(f"  {agent_r['detail']}")
        lines.append("")

    lines.append("━" * 28)
    lines.append(f"💡 关注指数：{' | '.join(idx['name'] for idx in all_index_results)}")
    lines.append(f"⏰ 报告生成于 {now.strftime('%H:%M:%S')}")

    return "\n".join(lines)


def simple_report(index_results: list[dict]) -> str:
    """简洁版报告（适配飞书消息）"""
    now = datetime.now()
    lines = []
    lines.append(f"📊 指数基金定投日报 | {now.strftime('%m-%d %A')}")
    lines.append("")

    for r in index_results:
        m = r["merge"]
        total = m["total_score"]
        dec = m["decision"]
        lines.append(
            f"{r['name']}：**{total:+.1f}** {dec}"
        )
        # 一行概况
        scores_str = " | ".join(
            f"{a['emoji']}{a['score']:+.0f}"
            for a in m["agents"]
        )
        lines.append(f"  {scores_str}")
        lines.append("")

    lines.append(f"⏰ {now.strftime('%H:%M')}")
    return "\n".join(lines)
