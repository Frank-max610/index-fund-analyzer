/* ══════════════════════════════════════════
   strategy.js — 策略规则页
   ══════════════════════════════════════════ */

const Strategy = {
  render(data) {
    if (!data) return;
    this.renderRules();
    this.renderThresholdChart(data);
    this.renderSignals(data);
  },

  renderRules() {
    const container = document.getElementById('rule-list');
    const rules = [
      { emoji: '📌', text: `每日固定投入 <strong>${CONFIG.BASE_AMOUNT} 元</strong>，所有策略围绕此规则设计` },
      { emoji: '🟢', text: `主力标的温度 <strong>< ${CONFIG.THRESHOLDS.primary_dca}%</strong> → 正常执行每日定投` },
      { emoji: '🟡', text: `主力标的温度 <strong>${CONFIG.THRESHOLDS.primary_dca}%~${CONFIG.THRESHOLDS.primary_hold}%</strong> → 维持持仓，正常定投` },
      { emoji: '🔴', text: `主力标的温度 <strong>> ${CONFIG.THRESHOLDS.primary_pause}%</strong> → 暂停定投，仅持有` },
      { emoji: '🔄', text: `中证A500温度 <strong>< ${CONFIG.THRESHOLDS.a500_switch}%</strong> → 切换主力定投方向至A500` },
      { emoji: '🎯', text: `沪深300温度 <strong>< ${CONFIG.THRESHOLDS.hs300_bottom}%</strong> → 可用资金抄底布局` },
      { emoji: '💎', text: `中证500温度 <strong>< ${CONFIG.THRESHOLDS.zz500_deep_value}%</strong> → 严重低估，可小仓位布局` },
    ];

    container.innerHTML = rules.map(r => `
      <div class="rule-item">
        <span class="rule-emoji">${r.emoji}</span>
        <span>${r.text}</span>
      </div>
    `).join('');
  },

  renderThresholdChart(data) {
    const temps = {};
    for (const [code, info] of Object.entries(data.indices)) {
      temps[code] = {
        name: info.name,
        temp: info.composite_temperature,
      };
    }
    Charts.renderThresholdChart('threshold-chart', temps);
  },

  renderSignals(data) {
    const container = document.getElementById('strategy-signals');
    const decision = data.decision;

    let html = '';
    if (decision.alerts && decision.alerts.length > 0) {
      html += decision.alerts.map(a => `<div class="alert-item">⚠️ ${a}</div>`).join('');
    }

    for (const [code, info] of Object.entries(data.indices)) {
      const temp = info.composite_temperature;
      const tc = tempColor(temp);
      const isPrimary = code === decision.primary_target;

      html += `
        <div class="rule-item" style="${isPrimary ? 'border-left: 3px solid var(--accent-blue);' : ''}">
          <span class="rule-emoji">${info.signal_emoji || '⚪'}</span>
          <div>
            <strong>${info.name}</strong> ${isPrimary ? '(主力)' : ''}
            <span class="temp-${tc}" style="margin-left:8px;font-family:var(--font-mono);font-weight:700">
              ${fmtTemp(temp)}
            </span>
            <br>
            <span style="font-size:12px;color:var(--text-muted)">
              PE温度: ${fmtTemp(info.pe_temperature)} | PB温度: ${fmtTemp(info.pb_temperature)} |
              数据源: ${info.data_source || info.temperature_status || '--'}
              ${isPrimary ? '| <strong style="color:var(--accent-blue)">主力定投标的</strong>' : ''}
            </span>
          </div>
        </div>`;
    }

    container.innerHTML = html;
  },
};
