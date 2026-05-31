# -*- coding: utf-8 -*-
"""宏观指标：PMI/CPI/M2/利率打分"""
import numpy as np


def pmi_score(pmi: float) -> float:
    """PMI打分：>50扩张→利多股市"""
    if pmi >= 52:
        return 2.0
    elif pmi >= 51:
        return 1.0
    elif pmi >= 49:
        return 0.0
    elif pmi >= 48:
        return -1.0
    else:
        return -2.0


def cpi_score(cpi: float) -> float:
    """CPI打分：温和通胀(1-3%)最优，通缩(<0)或高通胀(>5%)不利"""
    if 1.0 <= cpi <= 3.0:
        return 1.0
    elif 0 <= cpi < 1.0:
        return 0.0
    elif cpi < 0:
        return -1.5
    elif cpi > 5:
        return -2.0
    else:
        return 0.0


def m2_score(m2: float) -> float:
    """M2增速打分：适度宽松(8-12%)利多"""
    if 10 <= m2 <= 14:
        return 2.0
    elif 8 <= m2 < 10:
        return 1.0
    elif 6 <= m2 < 8:
        return 0.0
    else:
        return -1.0


def liquidity_score(bond_10y: float) -> float:
    """利率打分：利率下行利多（股债跷跷板）"""
    if bond_10y < 2.5:
        return 2.0
    elif bond_10y < 2.8:
        return 1.0
    elif bond_10y < 3.2:
        return 0.0
    elif bond_10y < 3.8:
        return -1.0
    else:
        return -2.0


def macro_score(pmi: float, cpi: float, m2: float, bond_10y: float) -> dict:
    """综合宏观评分"""
    s_pmi = pmi_score(pmi)
    s_cpi = cpi_score(cpi)
    s_m2 = m2_score(m2)
    s_rate = liquidity_score(bond_10y)

    total = round(s_pmi * 0.25 + s_m2 * 0.30 + s_rate * 0.25 + s_cpi * 0.20, 1)

    return {
        "pmi": pmi,
        "cpi": cpi,
        "m2": m2,
        "bond_10y": bond_10y,
        "score": total,
        "detail": (
            f"PMI={pmi:.1f} | CPI={cpi:.1f}% | M2增速={m2:.1f}% | "
            f"10Y国债={bond_10y:.2f}%"
        ),
    }
