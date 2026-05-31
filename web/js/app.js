/* ══════════════════════════════════════════
   app.js — 应用外壳：路由、导航、初始化
   三端统一：桌面(Electron) | 本地开发 | 手机浏览器(GitHub Pages)
   ══════════════════════════════════════════ */

const App = {
  currentPage: 'dashboard',
  dailyData: null,
  isDesktop: !!(window.desktopAPI && window.desktopAPI.isDesktop),

  // ── 初始化 ──
  async init() {
    console.log(`[App] 初始化... 环境: ${this.isDesktop ? '桌面端' : 'Web端'}`);

    this.setupNavigation();

    // 桌面端：监听 Git 同步结果
    if (this.isDesktop) {
      this.setupDesktop();
    } else {
      // Web端：注册 Service Worker（PWA离线支持）
      this.registerSW();
    }

    // 加载数据
    await this.loadData();

    // 初始化各子页面
    History.init();
    Manual.init();

    console.log('[App] 初始化完成');
  },

  // ── 桌面端专属设置 ──
  setupDesktop() {
    // 监听启动时的 Git 同步结果
    window.desktopAPI.on('git:syncResult', (result) => {
      if (result && result.success) {
        console.log('[App] 启动同步成功:', result.output);
        // 同步成功后重新加载数据
        this.loadData();
      }
    });

    // 在 header 添加同步按钮
    const headerRight = document.querySelector('.header-right');
    const syncBtn = document.createElement('span');
    syncBtn.id = 'desktop-sync-btn';
    syncBtn.style.cssText = 'cursor:pointer;font-size:14px;margin-left:4px;';
    syncBtn.title = 'Git 同步 (git pull)';
    syncBtn.textContent = '🔄';
    syncBtn.addEventListener('click', () => this.desktopSync());
    headerRight.insertBefore(syncBtn, headerRight.firstChild);

    console.log('[App] 桌面功能已激活');
  },

  async desktopSync() {
    const btn = document.getElementById('desktop-sync-btn');
    if (btn) btn.textContent = '⏳';
    const result = await API.syncGit();
    if (btn) btn.textContent = '🔄';
    if (result && result.success) {
      await this.loadData();
      alert('✅ 数据同步成功');
    } else {
      alert('❌ 同步失败: ' + (result ? result.output : '未知错误'));
    }
  },

  // ── 底部导航 ──
  setupNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const page = btn.dataset.page;
        this.navigateTo(page);
      });
    });

    window.addEventListener('hashchange', () => {
      const page = location.hash.replace('#', '') || 'dashboard';
      this.switchPage(page, false);
    });

    const hash = location.hash.replace('#', '');
    if (hash && ['dashboard', 'strategy', 'history', 'profit', 'manual'].includes(hash)) {
      this.navigateTo(hash);
    }
  },

  navigateTo(page) {
    location.hash = page;
    this.switchPage(page, true);
  },

  switchPage(page, updateNav) {
    this.currentPage = page;

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.add('active');

    if (updateNav) {
      document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.page === page);
      });
    }

    this.renderPage(page);
    document.getElementById('app-content').scrollTop = 0;
  },

  renderPage(page) {
    if (!this.dailyData && page !== 'manual') return;

    switch (page) {
      case 'dashboard': Dashboard.render(this.dailyData); break;
      case 'strategy': Strategy.render(this.dailyData); break;
      case 'history':
        History.loadDate(todayStr());
        History.renderAvailableDates();
        break;
      case 'profit': Profit.render(); break;
      case 'manual': break;
    }
  },

  // ── 数据加载 ──
  async loadData() {
    document.getElementById('sync-status').textContent = '🟡';

    try {
      this.dailyData = await API.fetchLatest();
      if (this.dailyData) {
        const displayDate = this.dailyData._actual_date || this.dailyData.date;
        document.getElementById('last-update').textContent = displayDate;
        document.getElementById('sync-status').textContent = '🟢';

        const dates = Storage.getAvailableDates();
        if (!dates.includes(displayDate)) {
          dates.push(displayDate);
          Storage.setAvailableDates(dates);
        }

        this.renderPage(this.currentPage);
      } else {
        document.getElementById('sync-status').textContent = '🔴';
        document.getElementById('last-update').textContent = '无数据';
      }
    } catch (err) {
      console.error('[App] 数据加载失败:', err);
      document.getElementById('sync-status').textContent = '🔴';
    }
  },

  // ── Service Worker（仅Web端） ──
  registerSW() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js')
        .then(reg => console.log('[SW] 注册成功:', reg.scope))
        .catch(err => console.warn('[SW] 注册失败:', err));
    }
  },
};

// ── 启动 ──
document.addEventListener('DOMContentLoaded', () => App.init());

// ── 手动刷新按钮 ──
document.getElementById('sync-status').addEventListener('click', () => App.loadData());
document.getElementById('sync-status').style.cursor = 'pointer';
document.getElementById('sync-status').title = '点击刷新数据';
