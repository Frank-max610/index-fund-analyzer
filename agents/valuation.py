# -*- coding: utf-8 -*-
"""估值分析师"""
from .base import BaseAgent
from data.fetcher import fetch_index_pe_pb, bond_yield_10y
from indicators.valuation import valuation_score


class ValuationAgent(BaseAgent):
    name = "valuation"
    emoji = "📈"

    def fetch_data(self, code: str, extra: dict = None):
        val = fetch_index_pe_pb(code)
        bond = bond_yield_10y()
        return {"val": val, "bond_yield": bond}

    def calc_indicators(self, data: dict) -> dict:
        return data

    def score(self, indicators: dict) -> dict:
        val = indicators["val"]
        bond = indicators["bond_yield"]
        pe = val.get("pe") or 20
        pe_pct = val.get("pe_percentile") or 0.5
        pb_pct = val.get("pb_percentile") or 0.5
        return valuation_score(pe, pe_pct, pb_pct, bond)
