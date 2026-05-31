/**
 * 指数基金量化助手 — Preload 脚本
 *
 * 通过 contextBridge 安全地向渲染进程暴露 IPC API。
 * 桌面端通过 window.desktopAPI 调用，Web端此对象不存在，
 * 因此 web/js/api.js 会自动回退到 HTTP 模式。
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktopAPI', {
  // ── 检测是否为桌面环境 ──
  isDesktop: true,

  // ── Git 操作 ──
  git: {
    pull: () => ipcRenderer.invoke('git:pull'),
    push: (message) => ipcRenderer.invoke('git:push', message),
    status: () => ipcRenderer.invoke('git:status'),
  },

  // ── 文件读写 ──
  fs: {
    readJSON: (filePath) => ipcRenderer.invoke('fs:readJSON', filePath),
    writeJSON: (filePath, data) => ipcRenderer.invoke('fs:writeJSON', filePath, data),
    listDailyFiles: () => ipcRenderer.invoke('fs:listDailyFiles'),
    exportCSV: (filePath, content) => ipcRenderer.invoke('fs:exportCSV', { filePath, content }),
  },

  // ── 对话框 ──
  dialog: {
    saveFile: (options) => ipcRenderer.invoke('dialog:saveFile', options),
  },

  // ── 应用信息 ──
  app: {
    getInfo: () => ipcRenderer.invoke('app:getInfo'),
  },

  // ── Shell ──
  shell: {
    openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  },

  // ── 事件监听 ──
  on: (channel, callback) => {
    const validChannels = ['git:syncResult'];
    if (validChannels.includes(channel)) {
      ipcRenderer.on(channel, (_event, ...args) => callback(...args));
    }
  },
});
