# -*- coding: utf-8 -*-
"""技术分析师"""
from .base import BaseAgent
from data.fetcher import index_daily
from indicators.technical import technical_score


class TechnicalAgent(BaseAgent):
    name = "technical"
    emoji = "📉"

    def fetch_data(self, code: str, extra: dict = None):
        df = index_daily(code, days=250)
        return {"df": df}

    def calc_indicators(self, data: dict) -> dict:
        return data

    def score(self, indicators: dict) -> dict:
        df = indicators["df"]
        if df.empty:
            return {"score": 0, "detail": "数据缺失"}
        return technical_score(
            df["close"], df["high"], df["low"], df["volume"]
        )
