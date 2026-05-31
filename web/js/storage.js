/* ══════════════════════════════════════════
   storage.js — localStorage 读写封装
   ══════════════════════════════════════════ */

const Storage = {
  // ── 每日数据缓存 ──
  cacheKey(date) {
    return `daily_${date}`;
  },

  getDaily(date) {
    try {
      const raw = localStorage.getItem(this.cacheKey(date));
      if (!raw) return null;
      const { data, cachedAt } = JSON.parse(raw);
      const age = (Date.now() - cachedAt) / 1000 / 60;
      if (age > CONFIG.CACHE_TTL_MINUTES) return null;
      return data;
    } catch {
      return null;
    }
  },

  setDaily(date, data) {
    try {
      localStorage.setItem(this.cacheKey(date), JSON.stringify({
        data,
        cachedAt: Date.now(),
      }));
    } catch {
      // localStorage 满了，清理旧数据
      this.cleanup();
    }
  },

  // ── 手动操作记录 ──
  getManualRecords() {
    try {
      return JSON.parse(localStorage.getItem('manual_records') || '[]');
    } catch {
      return [];
    }
  },

  addManualRecord(record) {
    const records = this.getManualRecords();
    records.unshift({ ...record, id: Date.now(), savedAt: new Date().toISOString() });
    localStorage.setItem('manual_records', JSON.stringify(records));
    return records;
  },

  deleteManualRecord(id) {
    const records = this.getManualRecords().filter(r => r.id !== id);
    localStorage.setItem('manual_records', JSON.stringify(records));
    return records;
  },

  // ── 可用日期列表 ──
  getAvailableDates() {
    try {
      return JSON.parse(localStorage.getItem('available_dates') || '[]');
    } catch {
      return [];
    }
  },

  setAvailableDates(dates) {
    localStorage.setItem('available_dates', JSON.stringify(dates));
  },

  // ── 清理过期缓存 ──
  cleanup() {
    const keys = Object.keys(localStorage).filter(k => k.startsWith('daily_'));
    if (keys.length > CONFIG.MAX_DAILY_CACHE) {
      // 保留最新的90天
      const sorted = keys.sort().reverse();
      sorted.slice(CONFIG.MAX_DAILY_CACHE).forEach(k => localStorage.removeItem(k));
    }
  },
};
