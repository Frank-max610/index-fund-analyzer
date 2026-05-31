/**
 * 指数基金量化助手 — Electron 主进程
 *
 * 功能：
 * - 加载 web/ SPA 作为渲染层
 * - 启动时自动 git pull 同步数据
 * - 系统托盘（最小化到托盘+状态显示）
 * - IPC：文件读写、Git 操作
 */

const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { execSync, exec } = require('child_process');

// ═══════════════ 路径配置 ═══════════════
const ROOT_DIR = path.join(__dirname, '..');
const WEB_DIR = path.join(ROOT_DIR, 'web');
const DATA_DIR = path.join(ROOT_DIR, 'data');
const DAILY_DIR = path.join(DATA_DIR, 'daily');
const LEDGER_FILE = path.join(DATA_DIR, 'ledger.json');
const PORTFOLIO_FILE = path.join(DATA_DIR, 'portfolio_state.json');

let mainWindow = null;
let tray = null;
let isQuitting = false;

// ═══════════════ 创建主窗口 ═══════════════
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 420,
    height: 780,
    minWidth: 360,
    minHeight: 600,
    title: '指数基金量化助手',
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    backgroundColor: '#0f0f1a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    // 手机风格窗口
    autoHideMenuBar: true,
    frame: true,
  });

  // 加载 web SPA
  const indexPath = path.join(WEB_DIR, 'index.html');
  mainWindow.loadFile(indexPath);

  // 开发模式：打开 DevTools
  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  // 关闭到托盘
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ═══════════════ 系统托盘 ═══════════════
function createTray() {
  // 创建简单的 16x16 托盘图标
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  let trayIcon;
  try {
    trayIcon = nativeImage.createFromPath(iconPath);
    if (trayIcon.isEmpty()) {
      trayIcon = nativeImage.createEmpty();
    }
  } catch {
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip('指数基金量化助手');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: '同步数据 (git pull)',
      click: () => syncGit(),
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  // 双击托盘显示窗口
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ═══════════════ Git 操作 ═══════════════
function runGit(args, cwd = ROOT_DIR) {
  try {
    const result = execSync(`git ${args}`, {
      cwd,
      encoding: 'utf-8',
      timeout: 30000,
      windowsHide: true,
    });
    return { success: true, output: result.trim() };
  } catch (err) {
    return { success: false, output: err.stderr || err.message };
  }
}

function syncGit() {
  console.log('[Git] 开始同步...');
  const pull = runGit('pull --rebase');
  console.log('[Git] pull:', pull.output);
  return pull;
}

function commitAndPush(message) {
  console.log('[Git] 准备提交...');

  // 检查是否有变更
  const status = runGit('status --porcelain');
  if (!status.output) {
    console.log('[Git] 无变更，跳过提交');
    return { success: true, output: 'no changes' };
  }

  // add
  const add = runGit(`add ${DATA_DIR}`);
  if (!add.success) return add;

  // commit
  const commit = runGit(`commit -m "${message}"`);
  if (!commit.success) return commit;

  // push
  const push = runGit('push');
  console.log('[Git] push:', push.output);
  return push;
}

// ═══════════════ IPC 处理器 ═══════════════
function setupIPC() {
  // ── Git 同步 ──
  ipcMain.handle('git:pull', async () => {
    return syncGit();
  });

  ipcMain.handle('git:push', async (_event, message) => {
    return commitAndPush(message || '📝 手动录入更新');
  });

  ipcMain.handle('git:status', async () => {
    const status = runGit('status --porcelain');
    const log = runGit('log -1 --format=%ci');
    return {
      dirty: !!status.output,
      lastCommit: log.output || 'unknown',
    };
  });

  // ── 文件读写 ──
  ipcMain.handle('fs:readJSON', async (_event, filePath) => {
    try {
      const fullPath = path.join(ROOT_DIR, filePath);
      const raw = fs.readFileSync(fullPath, 'utf-8');
      return JSON.parse(raw);
    } catch (err) {
      return null;
    }
  });

  ipcMain.handle('fs:writeJSON', async (_event, filePath, data) => {
    try {
      const fullPath = path.join(ROOT_DIR, filePath);
      const dir = path.dirname(fullPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(fullPath, JSON.stringify(data, null, 2), 'utf-8');
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  // ── 读取每日数据列表 ──
  ipcMain.handle('fs:listDailyFiles', async () => {
    try {
      if (!fs.existsSync(DAILY_DIR)) return [];
      const files = fs.readdirSync(DAILY_DIR)
        .filter(f => f.endsWith('.json'))
        .map(f => f.replace('.json', ''))
        .sort();
      return files;
    } catch {
      return [];
    }
  });

  // ── 应用信息 ──
  ipcMain.handle('app:getInfo', async () => {
    return {
      version: app.getVersion(),
      name: app.getName(),
      dataDir: DATA_DIR,
      isPackaged: app.isPackaged,
    };
  });

  // ── 打开外部链接 ──
  ipcMain.handle('shell:openExternal', async (_event, url) => {
    return shell.openExternal(url);
  });

  // ── 导出数据 ──
  ipcMain.handle('fs:exportCSV', async (_event, { filePath, content }) => {
    try {
      fs.writeFileSync(filePath, content, 'utf-8');
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  ipcMain.handle('dialog:saveFile', async (_event, options) => {
    const result = await dialog.showSaveDialog(mainWindow, options);
    return result;
  });
}

// ═══════════════ 应用生命周期 ═══════════════
app.whenReady().then(async () => {
  setupIPC();
  createWindow();
  createTray();

  // 启动时自动同步
  console.log('[App] 启动完成，开始同步数据...');
  const syncResult = syncGit();
  if (mainWindow) {
    mainWindow.webContents.on('did-finish-load', () => {
      mainWindow.webContents.send('git:syncResult', syncResult);
    });
  }
});

app.on('window-all-closed', () => {
  // Windows 上不退出，保持在托盘
});

app.on('before-quit', () => {
  isQuitting = true;
});

app.on('activate', () => {
  if (mainWindow) {
    mainWindow.show();
  }
});
