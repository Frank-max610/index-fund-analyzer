# -*- coding: utf-8 -*-
"""Agent 基类"""
from datetime import datetime


class BaseAgent:
    name: str = "base"
    emoji: str = "📊"

    def __init__(self):
        self.result = {}

    def fetch_data(self, code: str) -> dict:
        raise NotImplementedError

    def calc_indicators(self, data: dict) -> dict:
        raise NotImplementedError

    def score(self, indicators: dict) -> dict:
        raise NotImplementedError

    def signal(self, score_dict: dict) -> str:
        s = score_dict.get("score", 0)
        if s >= 2:
            return "🟢 强烈看多"
        elif s >= 1:
            return "🟡 偏多"
        elif s > -1:
            return "⚪ 中性"
        elif s > -2:
            return "🟠 偏空"
        else:
            return "🔴 强烈看空"

    def run(self, code: str, extra: dict = None) -> dict:
        """执行全流程"""
        data = self.fetch_data(code, extra)
        indicators = self.calc_indicators(data)
        score_dict = self.score(indicators)
        return {
            "agent": self.name,
            "emoji": self.emoji,
            "score": score_dict.get("score", 0),
            "detail": score_dict.get("detail", ""),
            "signal": self.signal(score_dict),
            "indicators": score_dict,
            "timestamp": datetime.now().isoformat(),
        }
