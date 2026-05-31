/* ══════════════════════════════════════════
   dashboard.js — 首页看板
   ══════════════════════════════════════════ */

const Dashboard = {
  async render(data) {
    if (!data) {
      document.getElementById('dashboard-loading').innerHTML =
        '<p style="color:#ff4757">⚠️ 数据加载失败，请检查网络连接或稍后再试</p>';
      return;
    }

    document.getElementById('dashboard-loading').style.display = 'none';
    document.getElementById('dashboard-content').style.display = 'block';

    this.renderSignal(data.decision);
    this.renderGauges(data.indices, data.decision);
    this.renderTable(data.indices);
    this.renderStats();
  },

  renderSignal(decision) {
    const card = document.getElementById('signal-card');
    const isBuy = decision.action === 'DCA_NORMAL';
    card.className = 'card signal-card ' + (isBuy ? 'dca-normal' : 'dca-pause');

    document.getElementById('signal-icon').textContent = isBuy ? '✅' : '⏸️';
    document.getElementById('signal-title').textContent = decision.action_label;

    let detail = `主力标的：${decision.primary_name}`;
    if (decision.alerts && decision.alerts.length > 0) {
      detail += '\n' + decision.alerts.join('\n');
    }
    document.getElementById('signal-detail').textContent = detail;

    const amt = document.getElementById('signal-amount');
    amt.textContent = isBuy ? `${decision.amount} 元/日` : '暂停';
    amt.className = 'signal-amount ' + (isBuy ? 'buy' : 'pause');
  },

  renderGauges(indices, decision) {
    const container = document.getElementById('temp-gauges');
    const primary = decision.primary_target;

    let html = '';
    for (const [code, info] of Object.entries(indices)) {
      const temp = info.composite_temperature;
      const tc = tempColor(temp);
      const emoji = tempEmoji(temp);
      const isPrimary = code === primary;
      const label = isPrimary ? `⭐ ${info.name}` : info.name;

      html += `
        <div class="temp-gauge" style="${isPrimary ? 'border: 1px solid var(--accent-blue);' : ''}">
          <div class="gauge-label">${label}</div>
          <div class="gauge-value temp-${tc}">${fmtTemp(temp)}</div>
          <div class="gauge-bar">
            <div class="gauge-fill fill-${tc}" style="width:${Math.min(temp || 0, 100)}%"></div>
          </div>
          <div class="gauge-signal">${emoji} ${info.signal || ''}</div>
        </div>`;
    }
    container.innerHTML = html;
  },

  renderTable(indices) {
    const container = document.getElementById('index-table');
    const rows = Object.entries(indices).map(([code, info]) => {
      return `
        <tr>
          <td><span class="index-name">${info.name}</span></td>
          <td><span class="index-role">${info.role || ''}</span></td>
          <td style="font-family:var(--font-mono)">${info.close || '--'}</td>
          <td style="color:${(info.chg_pct || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">
            ${fmtPct(info.chg_pct)}</td>
          <td style="font-family:var(--font-mono)">${info.pe || '--'}</td>
          <td style="font-family:var(--font-mono)">${info.pb || '--'}</td>
          <td style="font-family:var(--font-mono);font-weight:700"
              class="temp-${tempColor(info.composite_temperature)}">
            ${fmtTemp(info.composite_temperature)}</td>
          <td>${info.signal_emoji || ''} ${info.signal || ''}</td>
        </tr>`;
    }).join('');

    container.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>指数</th><th>角色</th><th>收盘</th><th>涨跌</th>
            <th>PE</th><th>PB</th><th>温度</th><th>信号</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  },

  async renderStats() {
    // 尝试加载持仓数据
    const portfolio = await API.fetchPortfolio();
    if (portfolio) {
      document.getElementById('stat-invested').textContent = fmtMoney(portfolio.total_invested);
      document.getElementById('stat-value').textContent = fmtMoney(portfolio.current_value);
      const pnl = portfolio.unrealized_pnl;
      const pnlEl = document.getElementById('stat-pnl');
      pnlEl.textContent = fmtMoney(pnl);
      pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
      const pctEl = document.getElementById('stat-pnl-pct');
      pctEl.textContent = fmtPct(portfolio.unrealized_pnl_pct);
      pctEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
    } else {
      // 尝试从本地记录计算
      const records = Storage.getManualRecords();
      const invested = records
        .filter(r => r.action === '定投' || r.action === '加仓')
        .reduce((sum, r) => sum + parseFloat(r.amount || 0), 0);
      document.getElementById('stat-invested').textContent = fmtMoney(invested);
      document.getElementById('stat-value').textContent = '--';
      document.getElementById('stat-pnl').textContent = '--';
      document.getElementById('stat-pnl-pct').textContent = '--';
    }
  },
};
