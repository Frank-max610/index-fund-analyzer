# -*- coding: utf-8 -*-
"""情绪分析师"""
from .base import BaseAgent
from data.fetcher import market_stats, index_daily
from indicators.sentiment import sentiment_score


class SentimentAgent(BaseAgent):
    name = "sentiment"
    emoji = "😱"

    def fetch_data(self, code: str, extra: dict = None):
        ms = market_stats()
        df = index_daily(code, days=10)
        return {"market": ms, "df": df}

    def calc_indicators(self, data: dict) -> dict:
        return data

    def score(self, indicators: dict) -> dict:
        ms = indicators["market"]
        df = indicators["df"]
        close = df.get("close") if not df.empty else None
        return sentiment_score(ms, close)
