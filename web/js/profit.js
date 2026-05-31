/* ══════════════════════════════════════════
   profit.js — 收益看板页
   ══════════════════════════════════════════ */

const Profit = {
  async render() {
    this.renderSummary();
    await this.renderChart();
    await this.renderRecords();
  },

  async renderSummary() {
    const container = document.getElementById('profit-summary');
    const portfolio = await API.fetchPortfolio();

    if (!portfolio) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:12px;">暂无云端持仓数据。请在手动录入页添加交易记录。</p>';
      return;
    }

    const pnl = portfolio.unrealized_pnl;
    const pnlPct = portfolio.unrealized_pnl_pct;

    container.innerHTML = `
      <div class="profit-item">
        <span class="profit-label">累计投入</span>
        <span class="profit-value">${fmtMoney(portfolio.total_invested)}</span>
      </div>
      <div class="profit-item">
        <span class="profit-label">持仓市值</span>
        <span class="profit-value">${fmtMoney(portfolio.current_value)}</span>
      </div>
      <div class="profit-item">
        <span class="profit-label">浮动盈亏</span>
        <span class="profit-value" style="color:${pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">
          ${fmtMoney(pnl)}</span>
      </div>
      <div class="profit-item">
        <span class="profit-label">收益率</span>
        <span class="profit-value" style="color:${pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">
          ${fmtPct(pnlPct)}</span>
      </div>`;

    // Position details
    if (portfolio.positions && portfolio.positions.length > 0) {
      let posHtml = portfolio.positions.map(p => `
        <div style="font-size:12px;margin-top:8px;padding:8px;background:var(--bg-secondary);border-radius:var(--radius-sm)">
          <strong>${p.fund_code}</strong> ${p.fund_name || ''}<br>
          持仓份额: ${p.total_shares} | 成本均价: ${p.avg_cost} | 投入: ${fmtMoney(p.total_invested)}
        </div>
      `).join('');
      container.innerHTML += posHtml;
    }
  },

  async renderChart() {
    const ledger = await API.fetchLedger();
    if (!ledger || !ledger.records || ledger.records.length === 0) {
      document.getElementById('profit-chart-container').innerHTML =
        '<p style="text-align:center;color:var(--text-muted);padding:60px 0;">暂无交易记录</p>';
      return;
    }
    Charts.renderProfitChart('profit-chart', ledger.records);
  },

  async renderRecords() {
    const container = document.getElementById('tx-records');

    // 云端账本
    const ledger = await API.fetchLedger();
    // 本地记录
    const local = Storage.getManualRecords();

    let html = '';

    if (ledger && ledger.records && ledger.records.length > 0) {
      html += '<p style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">📡 云端记录</p>';
      ledger.records.slice(-20).reverse().forEach(r => {
        html += `
          <div class="tx-record">
            <span class="tx-date">${r.date}</span>
            <span class="tx-action">${r.action}</span>
            <span class="tx-amount">+${r.amount}元</span>
            <span class="tx-detail">@${r.nav_at_action} → ${r.shares_acquired}份</span>
          </div>`;
      });
    }

    if (local.length > 0) {
      html += '<p style="font-size:11px;color:var(--text-muted);margin:12px 0 8px;">📱 本地记录</p>';
      local.slice(0, 20).forEach(r => {
        html += `
          <div class="tx-record">
            <span class="tx-date">${r.date}</span>
            <span class="tx-action">${r.action}</span>
            <span class="tx-amount">${r.amount}元</span>
            <span class="tx-detail">${r.fund_code || ''} ${r.note || ''}</span>
          </div>`;
      });
    }

    if (!html) {
      html = '<p style="color:var(--text-muted);font-size:12px;">暂无交易记录。开始在支付宝定投后，在此查看记录。</p>';
    }

    container.innerHTML = html;
  },
};
