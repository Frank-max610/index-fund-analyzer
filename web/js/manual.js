/* ══════════════════════════════════════════
   manual.js — 手动操作录入页
   ══════════════════════════════════════════ */

const Manual = {
  init() {
    document.getElementById('mf-date').value = todayStr();

    document.getElementById('manual-form').onsubmit = (e) => {
      e.preventDefault();
      this.saveRecord();
    };

    this.renderRecords();
  },

  saveRecord() {
    const record = {
      date: document.getElementById('mf-date').value,
      fund_code: document.getElementById('mf-fund').value,
      action: document.getElementById('mf-action').value,
      amount: parseFloat(document.getElementById('mf-amount').value) || 0,
      nav: parseFloat(document.getElementById('mf-nav').value) || null,
      note: document.getElementById('mf-note').value || '',
    };

    if (!record.date || record.amount <= 0) {
      alert('请填写日期和金额');
      return;
    }

    Storage.addManualRecord(record);
    this.renderRecords();

    // 重置表单
    document.getElementById('mf-amount').value = '10';
    document.getElementById('mf-nav').value = '';
    document.getElementById('mf-note').value = '';

    // 短暂提示
    const btn = document.querySelector('#manual-form .btn');
    const orig = btn.textContent;
    btn.textContent = '✅ 已保存';
    btn.style.background = 'var(--accent-green)';
    setTimeout(() => {
      btn.textContent = orig;
      btn.style.background = '';
    }, 1500);
  },

  renderRecords() {
    const container = document.getElementById('manual-records');
    const records = Storage.getManualRecords();

    if (records.length === 0) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:12px;">暂无本地记录。在支付宝完成交易后，在此录入。</p>';
      return;
    }

    container.innerHTML = records.slice(0, 30).map(r => `
      <div class="tx-record">
        <span class="tx-date">${r.date}</span>
        <span class="tx-action">${r.action}</span>
        <span style="font-family:var(--font-mono);font-weight:600">${r.amount}元</span>
        <span class="tx-detail">${r.fund_code || ''} ${r.nav ? '@' + r.nav : ''} ${r.note || ''}</span>
        <button onclick="Manual.deleteRecord(${r.id})"
          style="background:none;border:none;cursor:pointer;font-size:14px;padding:0 4px;"
          title="删除">🗑️</button>
      </div>
    `).join('');
  },

  deleteRecord(id) {
    if (confirm('确定删除这条记录？')) {
      Storage.deleteManualRecord(id);
      this.renderRecords();
    }
  },
};
