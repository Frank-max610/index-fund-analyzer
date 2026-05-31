/* ══════════════════════════════════════════
   config.js — 前端配置（单一真相源）
   ══════════════════════════════════════════ */

const CONFIG = {
  // GitHub 仓库配置
  REPO_OWNER: 'Frank-max610',
  REPO_NAME: 'index-fund-analyzer',
  REPO_BRANCH: 'main',

  // 数据目录路径
  DATA_DIR: 'data',
  DAILY_DIR: 'data/daily',
  REPORTS_DIR: 'data/reports',
  LEDGER_FILE: 'data/ledger.json',
  PORTFOLIO_FILE: 'data/portfolio_state.json',

  // 缓存配置
  CACHE_TTL_MINUTES: 30,
  MAX_DAILY_CACHE: 90,  // 最多缓存90天数据

  // 指数温度阈值（与云端 config.py 保持一致）
  THRESHOLDS: {
    primary_dca: 50,
    primary_hold: 80,
    primary_pause: 80,
    a500_switch: 30,
    hs300_bottom: 20,
    zz500_deep_value: 15,
  },
  BASE_AMOUNT: 10,

  // 基金信息
  FUNDS: {
    '007466': { name: '华泰柏瑞红利低波联接A', index: 'H30269' },
  },
};

// 构建 GitHub Raw 数据 URL
function dataUrl(path) {
  return `https://raw.githubusercontent.com/${CONFIG.REPO_OWNER}/${CONFIG.REPO_NAME}/${CONFIG.REPO_BRANCH}/${path}`;
}

// 获取今日日期 YYYY-MM-DD
function todayStr() {
  const d = new Date();
  return d.toISOString().split('T')[0];
}

// 格式化金额
function fmtMoney(n) {
  if (n == null) return '--';
  return Number(n).toFixed(2) + ' 元';
}

// 格式化百分比
function fmtPct(n) {
  if (n == null) return '--';
  const v = Number(n);
  const sign = v >= 0 ? '+' : '';
  return sign + v.toFixed(2) + '%';
}

// 格式化温度
function fmtTemp(n) {
  if (n == null) return '--';
  return Number(n).toFixed(0) + '%';
}

// 温度颜色判断
function tempColor(temp) {
  if (temp == null) return 'muted';
  if (temp < 50) return 'cold';
  if (temp <= 80) return 'warm';
  return 'hot';
}

function tempEmoji(temp) {
  if (temp == null) return '⚪';
  if (temp < 50) return '🟢';
  if (temp <= 80) return '🟡';
  return '🔴';
}
