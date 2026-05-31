# -*- coding: utf-8 -*-
"""资金流分析师"""
from .base import BaseAgent
from data.fetcher import north_flow
from indicators.fund_flow import fund_flow_score


class FundFlowAgent(BaseAgent):
    name = "fund_flow"
    emoji = "💰"

    def fetch_data(self, code: str, extra: dict = None):
        nf = north_flow(days=30)
        return {"north_flow": nf}

    def calc_indicators(self, data: dict) -> dict:
        return data

    def score(self, indicators: dict) -> dict:
        return fund_flow_score(indicators["north_flow"])
