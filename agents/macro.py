# -*- coding: utf-8 -*-
"""宏观分析师"""
from .base import BaseAgent
from data.fetcher import macro_data, bond_yield_10y
from indicators.macro import macro_score


class MacroAgent(BaseAgent):
    name = "macro"
    emoji = "🏛"

    def fetch_data(self, code: str, extra: dict = None):
        macro = macro_data()
        bond = bond_yield_10y()
        return {"macro": macro, "bond_10y": bond}

    def calc_indicators(self, data: dict) -> dict:
        return data

    def score(self, indicators: dict) -> dict:
        m = indicators["macro"]
        bond = indicators["bond_10y"]
        return macro_score(
            m.get("pmi", 50),
            m.get("cpi", 2),
            m.get("m2", 8),
            bond,
        )
