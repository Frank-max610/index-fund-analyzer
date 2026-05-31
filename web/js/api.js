/* ══════════════════════════════════════════
   api.js — 数据加载层
   三端自适应：桌面(Electron IPC) | 本地开发(相对路径) | 云端(GitHub Raw)
   ══════════════════════════════════════════ */

const API = {
  // ── 检测运行环境 ──
  _isDesktop() {
    return !!(window.desktopAPI && window.desktopAPI.isDesktop);
  },

  _isLocal() {
    return location.hostname === 'localhost' || location.hostname === '127.0.0.1'
        || location.protocol === 'file:';
  },

  // ── 获取单日数据 ──
  async fetchDaily(date) {
    // 先查缓存
    const cached = Storage.getDaily(date);
    if (cached) {
      console.log(`[API] ${date} → 缓存命中`);
      return cached;
    }

    // 桌面端：通过 IPC 直接读本地文件（零网络延迟）
    if (this._isDesktop()) {
      try {
        const data = await window.desktopAPI.fs.readJSON(`${CONFIG.DAILY_DIR}/${date}.json`);
        if (data) {
          Storage.setDaily(date, data);
          console.log(`[API] ${date} → 桌面本地加载`);
          return data;
        }
      } catch (err) {
        console.warn(`[API] ${date} → 桌面加载失败:`, err);
      }
    }

    // 本地开发模式：HTTP fetch 相对路径
    if (this._isLocal()) {
      try {
        const localUrl = `../data/daily/${date}.json`;
        console.log(`[API] 本地加载: ${localUrl}`);
        const resp = await fetch(localUrl);
        if (resp.ok) {
          const data = await resp.json();
          Storage.setDaily(date, data);
          return data;
        }
      } catch {}
    }

    // 云端模式：GitHub Raw
    const url = dataUrl(`${CONFIG.DAILY_DIR}/${date}.json`);
    console.log(`[API] GitHub Raw: ${url}`);

    try {
      const resp = await fetch(url, {
        cache: 'no-cache',
        headers: { 'Accept': 'application/json' },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      Storage.setDaily(date, data);
      console.log(`[API] ${date} → 加载成功`);
      return data;
    } catch (err) {
      console.warn(`[API] ${date} → 加载失败: ${err.message}`);
      // 返回过期缓存
      try {
        const raw = localStorage.getItem(Storage.cacheKey(date));
        if (raw) {
          const { data: stale } = JSON.parse(raw);
          console.log(`[API] ${date} → 使用过期缓存`);
          return stale;
        }
      } catch {}
      return null;
    }
  },

  // ── 获取最新数据 ──
  async fetchLatest() {
    const today = todayStr();
    let data = await this.fetchDaily(today);
    if (data) return data;

    // 尝试扫描可用日期
    const dates = await this.scanAvailableDates();
    if (dates.length > 0) {
      const latest = dates[dates.length - 1];
      data = await this.fetchDaily(latest);
      if (data) {
        data._actual_date = latest;
        return data;
      }
    }
    return null;
  },

  // ── 通用 fetchJSON ──
  async _fetchJSON(remotePath) {
    // 桌面端：IPC 直接读
    if (this._isDesktop()) {
      try {
        return await window.desktopAPI.fs.readJSON(remotePath);
      } catch {}
    }
    // 本地模式：HTTP
    if (this._isLocal()) {
      try {
        const localUrl = `../${remotePath}`;
        const resp = await fetch(localUrl);
        if (resp.ok) return await resp.json();
      } catch {}
    }
    // 远程模式：GitHub Raw
    try {
      const url = dataUrl(remotePath);
      const resp = await fetch(url, { cache: 'no-cache' });
      if (resp.ok) return await resp.json();
    } catch (err) {
      console.warn(`[API] 加载失败: ${remotePath}`, err.message);
    }
    return null;
  },

  // ── 获取账本数据 ──
  fetchLedger() {
    return this._fetchJSON(CONFIG.LEDGER_FILE);
  },

  // ── 获取持仓状态 ──
  fetchPortfolio() {
    return this._fetchJSON(CONFIG.PORTFOLIO_FILE);
  },

  // ── 扫描可用日期 ──
  async scanAvailableDates() {
    // 桌面端：直接列目录
    if (this._isDesktop()) {
      try {
        const dates = await window.desktopAPI.fs.listDailyFiles();
        Storage.setAvailableDates(dates);
        return dates;
      } catch {}
    }

    // Web端：从缓存中收集
    const dates = [];
    for (let i = 0; i < 90; i++) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      if (Storage.getDaily(dateStr)) {
        dates.push(dateStr);
      }
    }
    const stored = Storage.getAvailableDates();
    return stored.length > dates.length ? stored : dates.reverse();
  },

  // ── 桌面端：Git 同步 ──
  async syncGit() {
    if (!this._isDesktop()) {
      console.log('[API] 非桌面环境，跳过 git 同步');
      return null;
    }
    try {
      return await window.desktopAPI.git.pull();
    } catch (err) {
      console.warn('[API] git pull 失败:', err);
      return null;
    }
  },

  // ── 桌面端：保存并推送 ──
  async commitAndPush(message) {
    if (!this._isDesktop()) return null;
    try {
      return await window.desktopAPI.git.push(message);
    } catch (err) {
      console.warn('[API] git push 失败:', err);
      return null;
    }
  },
};
