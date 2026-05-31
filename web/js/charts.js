/* ══════════════════════════════════════════
   charts.js — Chart.js 可视化封装
   ══════════════════════════════════════════ */

const Charts = {
  _instances: {},

  destroy(key) {
    if (this._instances[key]) {
      this._instances[key].destroy();
      delete this._instances[key];
    }
  },

  // ── 温度阈值对比图 ──
  renderThresholdChart(canvasId, temperatures) {
    this.destroy('threshold');
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const indices = ['H30269', '000510', '000300', '000905'];
    const names = indices.map(c => temperatures[c]?.name || c);
    const temps = indices.map(c => temperatures[c]?.temp ?? 0);
    const colors = temps.map(t => {
      if (t < 50) return CONFIG.THRESHOLDS.primary_dca <= 50 ? '#00d4aa' : '#ffa502';
      if (t <= 80) return '#ffa502';
      return '#ff4757';
    });

    this._instances.threshold = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: names,
        datasets: [
          {
            label: '当前温度 %',
            data: temps,
            backgroundColor: colors,
            borderRadius: 6,
            borderSkipped: false,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          annotation: {
            annotations: {
              line50: {
                type: 'line',
                xMin: 50, xMax: 50,
                borderColor: '#ffa502',
                borderWidth: 2,
                borderDash: [5, 5],
                label: {
                  display: true,
                  content: '定投线 50%',
                  position: 'start',
                },
              },
              line80: {
                type: 'line',
                xMin: 80, xMax: 80,
                borderColor: '#ff4757',
                borderWidth: 2,
                borderDash: [5, 5],
                label: {
                  display: true,
                  content: '暂停线 80%',
                  position: 'start',
                },
              },
            },
          },
        },
        scales: {
          x: {
            min: 0,
            max: 100,
            grid: { color: '#2a2a45' },
            ticks: { color: '#a0a0b8', callback: v => v + '%' },
          },
          y: {
            grid: { display: false },
            ticks: { color: '#e8e8f0' },
          },
        },
      },
    });
  },

  // ── 累计收益趋势图 ──
  renderProfitChart(canvasId, records) {
    this.destroy('profit');
    const canvas = document.getElementById(canvasId);
    if (!canvas || !records || records.length === 0) return;

    const ctx = canvas.getContext('2d');

    // 计算累计数据
    let invested = 0;
    const dates = [];
    const investedSeries = [];
    const valueSeries = []; // 需要当前净值估算

    records.forEach(r => {
      invested += r.amount;
      dates.push(r.date);
      investedSeries.push(invested);
    });

    this._instances.profit = new Chart(ctx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [
          {
            label: '累计投入',
            data: investedSeries,
            borderColor: '#4dabf7',
            backgroundColor: 'rgba(77,171,247,0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#a0a0b8', usePointStyle: true, pointStyleWidth: 8 },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#a0a0b8', maxTicksLimit: 8 },
          },
          y: {
            grid: { color: '#2a2a45' },
            ticks: { color: '#a0a0b8', callback: v => '¥' + v },
          },
        },
      },
    });
  },

  // ── 温度迷你趋势（30天K线） ──
  renderMiniTrend(containerId, closes, currentTemp) {
    const container = document.getElementById(containerId);
    if (!container || !closes || closes.length < 10) return;

    const canvas = document.createElement('canvas');
    canvas.style.width = '100%';
    canvas.style.height = '40px';
    container.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    const color = currentTemp < 50 ? '#00d4aa' : currentTemp <= 80 ? '#ffa502' : '#ff4757';

    // 计算最近30个点的涨跌趋势
    const recent = closes.slice(-30);
    const min = Math.min(...recent);
    const max = Math.max(...recent);
    const range = max - min || 1;
    const normalized = recent.map(v => (v - min) / range);

    // 简化：用CSS画小趋势线
    const points = normalized.map((v, i) => `${(i / (normalized.length - 1)) * 100},${(1 - v) * 100}`);
    const svgLine = `<svg width="100%" height="40" style="display:block">
      <polyline points="${points.join(' ')}"
        fill="none" stroke="${color}" stroke-width="1.5"
        vector-effect="non-scaling-stroke"/>
    </svg>`;

    container.innerHTML = svgLine;
  },
};
