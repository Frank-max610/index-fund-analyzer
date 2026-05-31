# -*- coding: utf-8 -*-
"""
指数基金量化辅助系统 — 统一配置（单一真相源）
遵循定稿规范：每日10元定投 + 指数温度切换策略
"""

# ========== 基准定投金额 ==========
BASE_AMOUNT = 10  # 每日固定投入（元）

# ========== 跟踪标的清单（4个） ==========
WATCH_INDICES = [
    {"code": "H30269", "name": "中证红利低波", "fund_code": "007466",
     "fund_name": "华泰柏瑞中证红利低波ETF联接A", "role": "主力定投",
     "proxy_code": "000922", "proxy_name": "中证红利"},  # PE/PB估值代理
    {"code": "000510", "name": "中证A500", "role": "切换备选"},
    {"code": "000300", "name": "沪深300", "role": "抄底观察"},
    {"code": "000905", "name": "中证500", "role": "成长观察"},
]

# ========== 指数温度交易阈值（硬性规则） ==========
THRESHOLDS = {
    # 主力标的（红利低波 H30269 / 007466）
    "primary_dca": 50,          # 温度 < 50%：正常执行每日10元定投
    "primary_hold": 80,         # 温度 50%~80%：维持持仓，正常定投
    "primary_pause": 80,        # 温度 > 80%：暂停定投，仅持有

    # A500 切换规则
    "a500_switch": 30,          # A500 温度 < 30%：切换主力到A500
                                # A500 温度回升 > 30%：切回红利低波

    # 沪深300 抄底规则
    "hs300_bottom": 20,         # 沪深300 温度 < 20%：可用资金抄底布局

    # 中证500 严重低估参考
    "zz500_deep_value": 15,     # 中证500 温度 < 15%：严重低估，可小仓位布局
}

# ========== 温度计算参数 ==========
TEMPERATURE_CONFIG = {
    "pe_weight": 0.6,           # PE权重
    "pb_weight": 0.4,           # PB权重
    "lookback_years": 5,        # 历史数据回溯年限
    "min_data_points": 60,      # 最少数据点数
}

# ========== 多维度Agent评分权重 ==========
SCORE_WEIGHTS = {
    "valuation": 0.25,          # 估值维度（PE/PB/股债利差）
    "technical": 0.15,          # 技术维度（MA/RSI/MACD）
    "macro": 0.20,              # 宏观维度（PMI/CPI/M2）
    "sentiment": 0.10,          # 情绪维度（市场涨跌比）
    "risk": 0.10,               # 风险维度（波动率/回撤）
    "fund_flow": 0.10,          # 资金维度（北向资金）
    "fundamentals": 0.10,       # 基本面维度（动量/稳定性）
}

# ========== 评分到决策的映射 ==========
DECISION_MAP = [
    (2.0, "强烈看多 → 加倍买入"),
    (1.0, "偏多 → 正常定投"),
    (-1.0, "中性 → 观望"),
    (-2.0, "偏空 → 减仓"),
    (-99.0, "强烈看空 → 清仓"),
]

# ========== 飞书通知 ==========
FEISHU_WEBHOOK_URL = ""  # 通过 GitHub Secret 注入，避免公开泄露

# ========== 数据库 ==========
DB_PATH = "cache.db"

# ========== 数据目录 ==========
DATA_DIR = "data"
DAILY_DIR = "data/daily"
REPORTS_DIR = "data/reports"
INDEX_SERIES_DIR = "data/index_series"
LEDGER_FILE = "data/ledger.json"
PORTFOLIO_STATE_FILE = "data/portfolio_state.json"
