/* ══════════════════════════════════════════
   history.js — 历史日报查询页
   ══════════════════════════════════════════ */

const History = {
  async init() {
    // 设置日期选择器默认值为今天
    document.getElementById('history-date-picker').value = todayStr();
    document.getElementById('history-date-picker').max = todayStr();

    // 加载按钮
    document.getElementById('history-load-btn').onclick = () => this.loadDate();
    document.getElementById('history-today-btn').onclick = () => {
      document.getElementById('history-date-picker').value = todayStr();
      this.loadDate();
    };

    // 渲染可用日期列表
    this.renderAvailableDates();
  },

  async loadDate(dateStr) {
    if (!dateStr) {
      dateStr = document.getElementById('history-date-picker').value;
    }
    if (!dateStr) return;

    const container = document.getElementById('history-report');
    container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载中...</p></div>';

    const data = await API.fetchDaily(dateStr);
    if (!data) {
      container.innerHTML = `<div class="alert-item">
        ⚠️ 未找到 ${dateStr} 的数据<br>
        <small>该日期可能为非交易日，或数据尚未生成</small>
      </div>`;
      return;
    }

    this.renderReport(data, container);
  },

  renderReport(data, container) {
    const dec = data.decision;
    const ref = data.reference_indicators || {};

    // 构建类似云端日报的格式
    let html = '';

    // 核心结论
    const isBuy = dec.action === 'DCA_NORMAL';
    html += `<h2>🎯 核心结论</h2>`;
    html += `<p><strong>${isBuy ? '✅' : '🔴'} ${dec.action_label}</strong></p>`;
    html += `<p>主力标的：<strong>${dec.primary_name}</strong> | 基金：<code>${dec.primary_fund_code || 'N/A'}</code></p>`;
    html += `<p>操作方向：${isBuy ? '✅ 正常定投' : '⏸️ 暂停定投'} | 参考金额：<strong style="font-family:var(--font-mono)">${dec.amount} 元</strong></p>`;

    if (dec.alerts && dec.alerts.length > 0) {
      html += dec.alerts.map(a => `<div class="alert-item">⚠️ ${a}</div>`).join('');
    }

    // 指数详情表
    html += `<h3>📈 各指数详情</h3>`;
    html += `<table><thead><tr>
      <th>指数</th><th>温度</th><th>收盘</th><th>今日</th><th>PE</th><th>PB</th><th>信号</th>
    </tr></thead><tbody>`;

    for (const [code, info] of Object.entries(data.indices || {})) {
      const tc = tempColor(info.composite_temperature);
      html += `<tr>
        <td>${info.signal_emoji || ''} ${info.name}</td>
        <td class="temp-${tc}" style="font-family:var(--font-mono);font-weight:700">${fmtTemp(info.composite_temperature)}</td>
        <td style="font-family:var(--font-mono)">${info.close || '--'}</td>
        <td style="color:${(info.chg_pct || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${fmtPct(info.chg_pct)}</td>
        <td style="font-family:var(--font-mono)">${info.pe || '--'}</td>
        <td style="font-family:var(--font-mono)">${info.pb || '--'}</td>
        <td>${info.signal || ''}</td>
      </tr>`;
    }
    html += `</tbody></table>`;

    // 参考指标
    html += `<h3>🌐 参考指标</h3>`;
    html += `<p style="font-size:12px;color:var(--text-muted)">
      国债: ${ref.bond_10y || '--'}% |
      市场广度: ${ref.market_breadth || '--'}% |
      北向5日: ${ref.north_flow_5d || '--'}亿<br>
      PMI: ${ref.pmi || '--'} | CPI: ${ref.cpi || '--'}% | M2: ${ref.m2 || '--'}%
    </p>`;

    html += `<p style="font-size:10px;color:var(--text-muted);margin-top:12px;">🤖 生成时间: ${data.generated_at || data.date}</p>`;

    container.innerHTML = html;
  },

  async renderAvailableDates() {
    const container = document.getElementById('available-dates');
    const dates = await API.scanAvailableDates();

    if (dates.length === 0) {
      container.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">暂无本地缓存数据，请先在Network连接状态下加载数据</p>';
      return;
    }

    // 只显示最近30天
    const recent = dates.slice(-30).reverse();
    container.innerHTML = recent.map(d =>
      `<span class="date-chip" data-date="${d}" onclick="History.loadDate('${d}')">${d.slice(5)}</span>`
    ).join('');
  },
};
