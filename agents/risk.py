# -*- coding: utf-8 -*-
"""风险评估师"""
from .base import BaseAgent
from data.fetcher import index_daily
from indicators.risk import risk_score


class RiskAgent(BaseAgent):
    name = "risk"
    emoji = "⚠️"

    def fetch_data(self, code: str, extra: dict = None):
        df = index_daily(code, days=250)
        return {"df": df}

    def calc_indicators(self, data: dict) -> dict:
        return data

    def score(self, indicators: dict) -> dict:
        df = indicators["df"]
        if df.empty:
            return {"score": 0, "detail": "数据缺失"}
        return risk_score(df["close"])
