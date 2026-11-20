/**
 * CacheMind Web Visualizer & Benchmark Suite
 * Group 17 - OS Project
 */

let hitRatioChart = null;
let evictionsChart = null;
let priorityQosChart = null;
let trajectoryChart = null;

document.addEventListener('DOMContentLoaded', () => {
  fetchState();
  initBenchmarkCharts();
});

function switchTab(tabName) {
  const tabs = ['visualizer', 'benchmarks', 'theory'];
  tabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const btn = document.getElementById(`tab-btn-${t}`);
    if (t === tabName) {
      el.classList.remove('hidden');
      btn.className = 'px-3 py-1.5 rounded-md bg-emerald-600 text-white shadow font-medium';
    } else {
      el.classList.add('hidden');
      btn.className = 'px-3 py-1.5 rounded-md text-slate-300 hover:text-white font-medium';
    }
  });

  if (tabName === 'benchmarks' && !hitRatioChart) {
    initBenchmarkCharts();
    runSimulation();
  }
}

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    if (data.status === 'success') {
      renderState(data.state);
    }
  } catch (err) {
    console.error('Error fetching state:', err);
  }
}

function renderState(state) {
  // Update KPI Bar
  const stats = state.stats;
  document.getElementById('kpi-hit-ratio').textContent = `${stats.hit_ratio}%`;
  document.getElementById('kpi-hits-misses').textContent = `${stats.hits} Hits / ${stats.misses} Misses`;
  document.getElementById('kpi-target-p').textContent = Number(state.target_p).toFixed(2);
  document.getElementById('kpi-pollution-shields').textContent = stats.pollution_filtered;
  document.getElementById('kpi-priority-shields').textContent = stats.priority_shields;
  document.getElementById('kpi-evictions').textContent = stats.evictions;
  document.getElementById('kpi-dirty-writes').textContent = stats.dirty_writebacks;

  // Render Queue Badges
  document.getElementById('t1-badge').textContent = `${state.t1_size} / target p=${state.target_p}`;
  document.getElementById('t2-badge').textContent = `${state.t2_size} blocks`;
  document.getElementById('b1-badge').textContent = `${state.b1_size} ghost keys`;
  document.getElementById('b2-badge').textContent = `${state.b2_size} ghost keys`;
  document.getElementById('probation-badge').textContent = `${state.probation_size} quarantined`;

  // Render Blocks
  renderBlockList('t1-container', state.t1_keys, 'cyan');
  renderBlockList('t2-container', state.t2_keys, 'emerald');
  renderGhostList('b1-container', state.b1_size, 'cyan');
  renderGhostList('b2-container', state.b2_size, 'emerald');
  renderBlockList('probation-container', state.probation_keys, 'amber');

  // Render Priority Tier Distribution
  const tiers = state.tier_distribution || {};
  const totalRes = (state.t1_size + state.t2_size + state.probation_size) || 1;
  const crit = tiers.CRITICAL || 0;
  const high = tiers.HIGH || 0;
  const norm = tiers.NORMAL || 0;
  const low = tiers.LOW || 0;

  document.getElementById('tier-cnt-critical').textContent = `${crit} pages`;
  document.getElementById('tier-cnt-high').textContent = `${high} pages`;
  document.getElementById('tier-cnt-normal').textContent = `${norm} pages`;
  document.getElementById('tier-cnt-low').textContent = `${low} pages`;

  document.getElementById('tier-bar-critical').style.width = `${(crit / totalRes) * 100}%`;
  document.getElementById('tier-bar-high').style.width = `${(high / totalRes) * 100}%`;
  document.getElementById('tier-bar-normal').style.width = `${(norm / totalRes) * 100}%`;
  document.getElementById('tier-bar-low').style.width = `${(low / totalRes) * 100}%`;
}

function renderBlockList(containerId, keys, colorTheme) {
  const container = document.getElementById(containerId);
  if (!keys || keys.length === 0) {
    container.innerHTML = `<span class="text-xs text-slate-500 italic">Queue is currently empty</span>`;
    return;
  }

  const borderClass = colorTheme === 'cyan' ? 'border-cyan-500/30' : colorTheme === 'emerald' ? 'border-emerald-500/30' : 'border-amber-500/30';
  const bgClass = colorTheme === 'cyan' ? 'bg-cyan-950/40 text-cyan-200' : colorTheme === 'emerald' ? 'bg-emerald-950/40 text-emerald-200' : 'bg-amber-950/40 text-amber-200';

  container.innerHTML = keys.map(k => `
    <div class="cache-block animate-pulse-new flex items-center gap-1.5 px-2.5 py-1 rounded-lg border ${borderClass} ${bgClass} text-xs font-mono shadow-sm">
      <i class="fa-solid fa-cube text-[10px] opacity-70"></i>
      <span class="font-bold">${k}</span>
    </div>
  `).join('');
}

function renderGhostList(containerId, count, colorTheme) {
  const container = document.getElementById(containerId);
  if (!count || count === 0) {
    container.innerHTML = `<span class="text-[11px] text-slate-600 italic">Empty</span>`;
    return;
  }

  const items = Array.from({ length: Math.min(count, 12) }, (_, i) => i + 1);
  container.innerHTML = items.map(idx => `
    <div class="px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-mono">
      ghost#${idx}
    </div>
  `).join('') + (count > 12 ? `<span class="text-[10px] text-slate-500">+${count - 12} more</span>` : '');
}

async function handleManualOp(e) {
  e.preventDefault();
  const submitter = e.submitter;
  const op = submitter ? submitter.value : 'get';
  const key = document.getElementById('input-key').value.trim();
  const priority = document.getElementById('select-priority').value;
  const is_write = document.getElementById('check-dirty').checked;

  if (!key) return;

  try {
    const res = await fetch('/api/manual_op', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operation: op, key, priority, is_write })
    });
    const data = await res.json();
    if (data.status === 'success') {
      renderState(data.state);
      showBanner(data);
    }
  } catch (err) {
    console.error('Error submitting operation:', err);
  }
}

function showBanner(data) {
  const banner = document.getElementById('op-banner');
  const bannerText = document.getElementById('op-banner-text');
  const bannerDetail = document.getElementById('op-banner-detail');

  banner.classList.remove('hidden');
  if (data.result_type === 'hit') {
    banner.className = 'mt-3 px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-between bg-emerald-500/20 text-emerald-300 border border-emerald-500/40';
    bannerText.innerHTML = `<i class="fa-solid fa-circle-check mr-1.5"></i> <b>CACHE HIT:</b> Page <code>${data.key}</code> found resident in memory!`;
  } else {
    banner.className = 'mt-3 px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-between bg-amber-500/20 text-amber-300 border border-amber-500/40';
    bannerText.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1.5"></i> <b>CACHE MISS:</b> Page <code>${data.key}</code> fetched from backing store.`;
  }

  if (data.evicted_key) {
    bannerDetail.textContent = `Evicted victim block: ${data.evicted_key}`;
  } else {
    bannerDetail.textContent = `No eviction necessary`;
  }

  setTimeout(() => { banner.classList.add('hidden'); }, 3500);
}

async function resetCache() {
  try {
    const res = await fetch('/api/reset?capacity=16', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      renderState(data.state);
      alert('Cache reset successfully with capacity 16!');
    }
  } catch (err) {
    console.error('Error resetting cache:', err);
  }
}

async function injectScanAttack() {
  const startIdx = Math.floor(Math.random() * 8000) + 1000;
  for (let i = 0; i < 15; i++) {
    const key = `scan_page_${startIdx + i}`;
    await fetch('/api/manual_op', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operation: 'put', key, priority: 'LOW', is_write: false })
    });
  }
  fetchState();
  alert('Injected 15 sequential scan pages with Priority LOW! Notice how CacheMind quarantined them into the Scan Probation Buffer, protecting active working sets in T1 & T2!');
}

async function injectMultiTenantBurst() {
  const tasks = [
    { key: 'kernel_sched_table', priority: 'CRITICAL', op: 'put', is_write: true },
    { key: 'kernel_interrupt_vect', priority: 'CRITICAL', op: 'get', is_write: false },
    { key: 'ui_render_buffer', priority: 'HIGH', op: 'put', is_write: true },
    { key: 'ui_event_queue', priority: 'HIGH', op: 'get', is_write: false },
    { key: 'worker_req_doc', priority: 'NORMAL', op: 'put', is_write: false },
    { key: 'worker_res_data', priority: 'NORMAL', op: 'get', is_write: false },
    { key: 'background_backup_1', priority: 'LOW', op: 'put', is_write: false },
  ];

  for (const t of tasks) {
    await fetch('/api/manual_op', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(t)
    });
  }
  fetchState();
}

// ================= BENCHMARK SIMULATION CHARTS =================

function initBenchmarkCharts() {
  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { size: 10 } } }
    },
    scales: {
      x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: '#334155' } },
      y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: '#334155' } }
    }
  };

  const ctxHit = document.getElementById('chart-hit-ratio')?.getContext('2d');
  if (ctxHit) {
    hitRatioChart = new Chart(ctxHit, {
      type: 'bar',
      data: {
        labels: ['FIFO', 'LRU', 'LFU', 'ARC', 'CacheMind'],
        datasets: [{
          label: 'Hit Ratio (%)',
          data: [0, 0, 0, 0, 0],
          backgroundColor: ['#64748b', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981'],
          borderRadius: 6
        }]
      },
      options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 100 } } }
    });
  }

  const ctxEvict = document.getElementById('chart-evictions')?.getContext('2d');
  if (ctxEvict) {
    evictionsChart = new Chart(ctxEvict, {
      type: 'bar',
      data: {
        labels: ['FIFO', 'LRU', 'LFU', 'ARC', 'CacheMind'],
        datasets: [{
          label: 'Total Evictions',
          data: [0, 0, 0, 0, 0],
          backgroundColor: ['#64748b', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981'],
          borderRadius: 6
        }]
      },
      options: commonOptions
    });
  }

  const ctxQos = document.getElementById('chart-priority-qos')?.getContext('2d');
  if (ctxQos) {
    priorityQosChart = new Chart(ctxQos, {
      type: 'bar',
      data: {
        labels: ['Kernel (CRITICAL)', 'Foreground (HIGH)', 'Apps (NORMAL)', 'Batch (LOW)'],
        datasets: [
          { label: 'Standard LRU', data: [0, 0, 0, 0], backgroundColor: '#f59e0b', borderRadius: 4 },
          { label: 'CacheMind (Shielded)', data: [0, 0, 0, 0], backgroundColor: '#10b981', borderRadius: 4 }
        ]
      },
      options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, max: 100 } } }
    });
  }

  const ctxTraj = document.getElementById('chart-trajectory')?.getContext('2d');
  if (ctxTraj) {
    trajectoryChart = new Chart(ctxTraj, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { label: 'CacheMind Target p', data: [], borderColor: '#10b981', tension: 0.2, pointRadius: 0 },
          { label: 'Classical ARC Target p', data: [], borderColor: '#8b5cf6', tension: 0.2, pointRadius: 0 }
        ]
      },
      options: commonOptions
    });
  }
}

async function runSimulation() {
  const btn = document.getElementById('btn-run-sim');
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Simulating Workload...`;

  const workload_type = document.getElementById('sim-workload').value;
  const capacity = parseInt(document.getElementById('sim-capacity').value) || 40;
  const num_requests = parseInt(document.getElementById('sim-requests').value) || 1500;

  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workload_type, capacity, num_requests })
    });
    const data = await res.json();
    if (data.status === 'success') {
      updateSimulationVisuals(data.results);
    }
  } catch (err) {
    console.error('Simulation error:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-play"></i> Run Simulation`;
  }
}

function updateSimulationVisuals(results) {
  const algos = results.map(r => r.algorithm);
  const hitRatios = results.map(r => r.hit_ratio);
  const evictions = results.map(r => r.evictions);

  if (hitRatioChart) {
    hitRatioChart.data.labels = algos;
    hitRatioChart.data.datasets[0].data = hitRatios;
    hitRatioChart.update();
  }

  if (evictionsChart) {
    evictionsChart.data.labels = algos;
    evictionsChart.data.datasets[0].data = evictions;
    evictionsChart.update();
  }

  // Priority QoS Chart (LRU vs CacheMind)
  const lru = results.find(r => r.algorithm === 'LRU');
  const cm = results.find(r => r.algorithm === 'CacheMind');

  if (lru && cm && priorityQosChart) {
    const calcRate = (res, pri) => {
      const h = res.priority_hit_breakdown[pri] || 0;
      const m = res.priority_miss_breakdown[pri] || 0;
      return (h + m) > 0 ? ((h / (h + m)) * 100).toFixed(1) : 0;
    };

    priorityQosChart.data.datasets[0].data = [
      calcRate(lru, 'CRITICAL'),
      calcRate(lru, 'HIGH'),
      calcRate(lru, 'NORMAL'),
      calcRate(lru, 'LOW')
    ];
    priorityQosChart.data.datasets[1].data = [
      calcRate(cm, 'CRITICAL'),
      calcRate(cm, 'HIGH'),
      calcRate(cm, 'NORMAL'),
      calcRate(cm, 'LOW')
    ];
    priorityQosChart.update();
  }

  // Trajectory Chart
  if (cm && cm.p_trajectory && trajectoryChart) {
    const stepSample = Math.max(1, Math.floor(cm.p_trajectory.length / 50));
    const sampledP = cm.p_trajectory.filter((_, idx) => idx % stepSample === 0);
    const labels = sampledP.map((_, i) => `${i * stepSample}`);

    trajectoryChart.data.labels = labels;
    trajectoryChart.data.datasets[0].data = sampledP;

    const arc = results.find(r => r.algorithm === 'ARC');
    if (arc && arc.p_trajectory) {
      trajectoryChart.data.datasets[1].data = arc.p_trajectory.filter((_, idx) => idx % stepSample === 0);
    }
    trajectoryChart.update();
  }

  // Populate Table
  const tbody = document.getElementById('sim-table-body');
  tbody.innerHTML = results.map(r => `
    <tr class="hover:bg-slate-800/40">
      <td class="px-4 py-2.5 font-bold ${r.algorithm === 'CacheMind' ? 'text-emerald-400 font-extrabold' : 'text-slate-200'}">
        ${r.algorithm} ${r.algorithm === 'CacheMind' ? '⭐' : ''}
      </td>
      <td class="px-4 py-2.5">${r.total_requests}</td>
      <td class="px-4 py-2.5 font-bold ${r.algorithm === 'CacheMind' ? 'text-emerald-400' : 'text-slate-300'}">${r.hit_ratio}%</td>
      <td class="px-4 py-2.5">${r.hits} / ${r.misses}</td>
      <td class="px-4 py-2.5">${r.evictions}</td>
      <td class="px-4 py-2.5">${r.dirty_writebacks}</td>
      <td class="px-4 py-2.5">${r.algorithm === 'CacheMind' ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-semibold text-[11px]">${r.pollution_filtered} attacks blocked</span>` : '<span class="text-slate-500">None (Polluted)</span>'}</td>
    </tr>
  `).join('');
}
