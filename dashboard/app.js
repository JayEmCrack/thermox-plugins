'use strict';
// ThermoX dashboard. All server text is inserted with textContent (never innerHTML).
const $ = id => document.getElementById(id);
let viewId = null;      // experiment being viewed; null = follow the running/latest one
let lastData = null;

async function api(path, opts) {
  const res = await fetch('api/' + path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || 'Request failed (' + res.status + ')');
  return body;
}
const post = (path, data) => api(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {}),
});

function setMsg(text, isErr) { const m = $('formMsg'); m.textContent = text; m.className = 'msg' + (isErr ? ' err' : ''); }
const parseTime = s => new Date(s.replace(' ', 'T'));

function setStat(id, text, cls) { const e = $(id); e.textContent = text; e.className = 'value' + (cls ? ' ' + cls : ''); }

function render(d) {
  lastData = d;
  const e = d.experiment, l = d.latest;
  if (!e) { $('expTitle').textContent = 'No experiment yet'; drawChart([], 0); return; }
  $('expTitle').textContent = '#' + e.id + ' ' + e.experiment_name + ' (' + e.mode + ', target ' + Number(e.target_temperature).toFixed(1) +
    ' °C) ' + (e.active ? '- running' : '- ended');

  setStat('vMode', e.mode, e.mode === 'HEATING' ? 'heat' : 'cool');
  if (l) {
    setStat('vTemp', Number(l.temperature).toFixed(1) + ' °C');
    setStat('vTarget', Number(l.target_temperature).toFixed(1) + ' °C');
    setStat('vPeltier', l.peltier_status == 1 ? 'ON' : 'OFF', l.peltier_status == 1 ? 'on' : '');
    setStat('vFan', l.fan_status == 1 ? 'ON' : 'OFF', l.fan_status == 1 ? 'on' : '');
    setStat('vBatt', l.battery_voltage === null ? 'not sensed' : Number(l.battery_voltage).toFixed(2) + ' V');
  } else {
    ['vTemp', 'vTarget', 'vPeltier', 'vFan', 'vBatt'].forEach(i => setStat(i, '--'));
  }

  // Connection badge: live only if the running experiment received a sample in the last 10 s.
  const conn = $('conn');
  let live = false;
  if (e.active && l) live = (parseTime(d.server_time) - parseTime(l.timestamp)) <= 10000;
  conn.textContent = live ? 'Receiving data' : (e.active ? 'Waiting for data' : 'No data');
  conn.className = 'badge ' + (live ? 'on' : 'off');

  const tb = document.querySelector('#history tbody');
  tb.replaceChildren();
  d.logs.slice(-50).reverse().forEach(r => {
    const tr = tb.insertRow();
    [r.timestamp, Number(r.temperature).toFixed(2), Number(r.target_temperature).toFixed(1),
     r.peltier_status == 1 ? 'ON' : 'OFF', r.fan_status == 1 ? 'ON' : 'OFF',
     r.battery_voltage === null ? '-' : Number(r.battery_voltage).toFixed(2)]
      .forEach(v => { tr.insertCell().textContent = v; });
  });
  drawChart(d.logs, e.id);
}

function drawChart(logs) {
  const c = $('chart'), dpr = window.devicePixelRatio || 1;
  const W = c.clientWidth, H = 300;
  c.width = W * dpr; c.height = H * dpr;
  const g = c.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  g.font = '12px system-ui, Arial'; g.fillStyle = '#66727f'; g.strokeStyle = '#dde2e8';
  const L = 46, R = 12, T = 10, B = 28, w = W - L - R, h = H - T - B;
  if (!logs.length) { g.fillText('No data yet', L + 10, T + 24); return; }

  const t0 = parseTime(logs[0].timestamp).getTime();
  const xs = logs.map(r => (parseTime(r.timestamp).getTime() - t0) / 1000);
  const tmax = Math.max(xs[xs.length - 1], 10);
  const vals = logs.flatMap(r => [Number(r.temperature), Number(r.target_temperature)]);
  let lo = Math.floor(Math.min(...vals) - 1), hi = Math.ceil(Math.max(...vals) + 1);
  const X = t => L + (t / tmax) * w, Y = v => T + h - ((v - lo) / (hi - lo)) * h;

  g.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const v = lo + ((hi - lo) * i) / 5, y = Y(v);
    g.beginPath(); g.moveTo(L, y); g.lineTo(L + w, y); g.stroke();
    g.fillText(v.toFixed(1), L - 6, y + 4);
  }
  g.textAlign = 'center';
  for (let i = 0; i <= 5; i++) {
    const t = (tmax * i) / 5;
    g.fillText(tmax >= 120 ? (t / 60).toFixed(1) + ' min' : t.toFixed(0) + ' s', X(t), H - 8);
  }
  const line = (key, color, dash) => {
    g.beginPath(); g.setLineDash(dash); g.strokeStyle = color; g.lineWidth = 2;
    logs.forEach((r, i) => { const x = X(xs[i]), y = Y(Number(r[key])); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.stroke(); g.setLineDash([]);
  };
  line('target_temperature', '#d9480f', [6, 4]);
  line('temperature', '#1f6feb', []);
}

async function refresh() {
  try {
    render(await api(viewId ? 'status.php?experiment_id=' + viewId : 'status.php'));
  } catch (err) { $('conn').textContent = 'Server error'; $('conn').className = 'badge off'; }
}

async function loadExperiments() {
  try {
    const { experiments } = await api('experiments.php');
    const tb = document.querySelector('#experiments tbody');
    tb.replaceChildren();
    experiments.forEach(x => {
      const tr = tb.insertRow();
      if (String(x.id) === String(viewId)) tr.className = 'sel';
      [x.id, x.experiment_name, x.mode, Number(x.target_temperature).toFixed(1) + ' °C', x.start_time,
       x.end_time || 'running', x.samples].forEach(v => { tr.insertCell().textContent = v; });
      const cell = tr.insertCell();
      const view = document.createElement('button');
      view.className = 'small secondary'; view.textContent = 'View';
      view.onclick = () => { viewId = x.id; refresh(); loadExperiments(); };
      const csv = document.createElement('a');
      csv.href = 'api/export.php?experiment_id=' + encodeURIComponent(x.id);
      csv.textContent = ' CSV'; csv.style.marginLeft = '8px';
      cell.append(view, csv);
    });
  } catch (err) { /* shown by refresh() */ }
}

$('startForm').addEventListener('submit', async ev => {
  ev.preventDefault();
  try {
    const r = await post('start_experiment.php', {
      experiment_name: $('expName').value, mode: $('expMode').value, target_temperature: Number($('expTarget').value),
    });
    viewId = null; setMsg('Experiment #' + r.experiment_id + ' started. Start the receiver to log data.');
    refresh(); loadExperiments();
  } catch (err) { setMsg(err.message, true); }
});

$('stopBtn').addEventListener('click', async () => {
  try { await post('stop_experiment.php'); setMsg('Experiment stopped.'); refresh(); loadExperiments(); }
  catch (err) { setMsg(err.message, true); }
});

window.addEventListener('resize', () => lastData && drawChart(lastData.logs));
refresh(); loadExperiments();
setInterval(refresh, 2000);
setInterval(loadExperiments, 10000);
