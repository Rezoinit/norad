// norad operator screen: devices, Polar setup, recording, markers, live timeline.
const socket = io();
const $ = id => document.getElementById(id);

// ── Timeline rows: which stream/channels each row draws (channel = column index) ──
const ROWS = [
  { title: 'Pupil L / R (mm) · 100 ms average', stream: 'norad_tobii', ch: [3, 4], colors: ['#f5c142', '#4a9eff'], gap: 0.15,
    robust: true, smooth: 0.1 },
  { title: 'Gaze x / y (0–1 of scene) · shaded = fixation', stream: 'norad_tobii', ch: [1, 2], colors: ['#3ecfb2', '#c9d6e3'],
    gap: 0.15, range: [0, 1], bands: { stream: 'norad_fixation', ch: 1 } },
  { title: 'Nasal L / R (mic amplitude)', stream: 'norad_nasal_env', ch: [0, 1], colors: ['#f5c142', '#4a9eff'], gap: 0.5 },
  { title: 'Heart rate (bpm)', stream: 'norad_polar_hr', ch: [0], colors: ['#ff9f6b'], gap: 5 },
  { title: 'ECG (µV)', stream: 'norad_polar_ecg', ch: [0], colors: ['#ff6b6b'], gap: 0.5 },
  { title: 'Chest motion (mg)', stream: 'norad_polar_acc', ch: [0], colors: ['#b48cff'], gap: 0.5,
    map: v => [Math.hypot(v[0], v[1], v[2])] },
];
const isMarkerStream = s => s.toLowerCase().includes('marker');
const KEEP_S = 70;

const buf = {};          // stream -> {t: [], v: []}
let clockOffset = null;  // LSL time - browser time (s)
let recording = false;

socket.on('data', d => {
  const off = d.now - performance.now() / 1000;
  clockOffset = clockOffset === null ? off : Math.max(off, clockOffset - 0.001);
  const b = buf[d.stream] || (buf[d.stream] = { t: [], v: [] });
  for (let i = 0; i < d.t.length; i++) { b.t.push(d.t[i]); b.v.push(d.v[i]); }
  const cut = d.now - KEEP_S;
  let k = 0; while (k < b.t.length && b.t[k] < cut) k++;
  if (k) { b.t.splice(0, k); b.v.splice(0, k); }
  const last = d.v[d.v.length - 1];
  if (d.stream === 'norad_polar_hr') $('n-hr').textContent = Math.round(last[0]);
  if (d.stream === 'norad_tobii') $('n-pupil').textContent = `${fmt(last[3])} / ${fmt(last[4])}`;
  if (d.stream === 'norad_fixation') {
    $('n-fix').textContent = last[1] ? Math.round(last[2] * 1000) : '–';
    $('n-fixrate').textContent = last[3];
  }
  if (isMarkerStream(d.stream)) d.v.forEach(v => logLine(v[1] ? `${v[0]}: ${v[1]}` : v[0], d.stream));
});

function fmt(v) { return Number.isFinite(v) ? v.toFixed(2) : '–'; }

// ── Status ──
socket.on('status', s => {
  const errs = [];
  for (const [k, st] of Object.entries(s.devices)) {
    $('dot-' + k).className = 'dot' + (st.connected ? ' ok' : st.error ? ' err' : '');
    $('rate-' + k).textContent = st.connected ? st.rate_hz + ' Hz' : '';
    if (st.error) errs.push(`${k}: ${st.error}`);
  }
  $('dot-lr').className = 'dot' + (s.labrecorder.available ? ' ok' : '');
  $('dev-errors').textContent = errs.join(' · ');
  if (s.polar_address) $('polar-saved').textContent = 'Saved strap: ' + s.polar_address;
  const r = s.recording;
  recording = r.active;
  $('btn-start').hidden = r.active;
  document.querySelectorAll('button.task').forEach(b => { b.disabled = r.active || s.task_running; });
  $('btn-stop').hidden = !r.active;
  $('rec-info').textContent = r.active ? `● ${Math.floor(r.elapsed_s / 60)}:${String(r.elapsed_s % 60).padStart(2, '0')}  ${r.folder}` : '';
  $('rec-streams').textContent = r.active ? 'Recording: ' + r.streams.map(n => n.replace('norad_', '')).join(', ') : '';
});
let msgTimer;
function say(m) { $('msg').textContent = m; clearTimeout(msgTimer); msgTimer = setTimeout(() => { $('msg').textContent = ''; }, 15000); }
socket.on('app_error', say);
socket.on('saved', folder => say('Saved: ' + folder));

// ── Devices + Polar setup ──
$('btn-connect').onclick = () => socket.emit('connect_devices', {});
$('btn-calibrate').onclick = () => {
  $('calib-msg').textContent = 'Calibrating… keep looking at the card centre.';
  socket.emit('tobii_calibrate', { participant: $('participant').value });
};
socket.on('tobii_calibration', r => {
  $('calib-msg').textContent = r.message;
  $('calib-msg').className = 'sub' + (r.ok ? '' : ' warn');
});
$('btn-participant').onclick = () => window.open('/participant', 'participant', 'width=800,height=600');
$('btn-scan').onclick = () => {
  $('polar-list').innerHTML = '<span class="sub">Scanning (5 s)…</span>';
  socket.emit('polar_scan', {});
};
socket.on('polar_devices', list => {
  const el = $('polar-list');
  el.innerHTML = list.length ? '' : '<span class="sub">No Polar H10 found. Is the strap on and wet?</span>';
  for (const d of list) {
    const b = document.createElement('button');
    b.textContent = d.name;
    b.onclick = () => { socket.emit('polar_connect', { address: d.address }); el.innerHTML = '<span class="sub">Connecting…</span>'; };
    el.appendChild(b);
  }
});

// ── Recording ──
$('participant').value = localStorage.getItem('participant') || '';
$('btn-start').onclick = () => {
  $('btn-start').disabled = true;  // one click = one recording
  setTimeout(() => { $('btn-start').disabled = false; }, 4000);
  localStorage.setItem('participant', $('participant').value);
  $('log').innerHTML = '';
  socket.emit('start', { participant: $('participant').value, task: $('task').value });
};
$('btn-stop').onclick = () => socket.emit('stop', {});
document.querySelectorAll('button.task').forEach(b => {
  b.onclick = () => {
    localStorage.setItem('participant', $('participant').value);
    $('log').innerHTML = '';
    socket.emit('task', { name: b.dataset.task, participant: $('participant').value });
  };
});

// ── Markers ──
const labels = JSON.parse(localStorage.getItem('labels') || '{}');
for (let k = 1; k <= 9; k++) {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<span class="key">${k}</span><input data-k="${k}" placeholder="label for key ${k}">`;
  const inp = row.querySelector('input');
  inp.value = labels[k] || '';
  inp.oninput = () => { labels[k] = inp.value; localStorage.setItem('labels', JSON.stringify(labels)); };
  $('labels').appendChild(row);
}
function mark(key, label, text = '') { socket.emit('marker', { key, label, text }); }
function logLine(text, stream) {
  const t = new Date().toLocaleTimeString();
  const src = stream === 'norad_markers' ? '' : ` (${stream})`;
  $('log').insertAdjacentHTML('afterbegin', `<div>${t} ${escapeHtml(text)}${src}${recording ? '' : ' · not recording'}</div>`);
}
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]); }

const MARK_KEYS = [' ', 'PageDown', 'PageUp', 'ArrowRight'];  // Space + presentation clickers
const NEVER_TYPED = ['PageDown', 'PageUp'];                     // clicker keys work even in a text field
let escAt = 0;
// Returns true if the key was used. Also called from the participant window.
window.handleKey = e => {
  if (e.repeat || e.metaKey || e.ctrlKey || e.altKey) return false;
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName);
  if (e.key === 'F5' && recording) return true;  // clicker "slideshow" button: never reload mid-recording
  if (e.key === 'Escape') {
    if (typing) { e.target.blur(); return true; }
    if (!recording) return true;
    if (Date.now() - escAt < 2000) socket.emit('stop', {});  // two presses: a clicker alone can't stop it
    else { escAt = Date.now(); say('Press Esc again to stop recording'); }
    return true;
  }
  if (typing && !NEVER_TYPED.includes(e.key)) {
    if (e.target.id === 'note' && e.key === 'Enter' && e.target.value.trim()) {
      mark('note', 'note', e.target.value.trim()); e.target.value = ''; e.target.blur();
    } else if (e.key === 'Enter') e.target.blur();
    return false;
  }
  if (MARK_KEYS.includes(e.key)) { mark('space', 'mark'); return true; }
  if (/^[1-9]$/.test(e.key)) { mark(e.key, labels[e.key] || e.key); return true; }
  return false;
};
document.addEventListener('keydown', e => { if (handleKey(e)) e.preventDefault(); });
$('win').onchange = () => $('win').blur();

// ── Drawing ──
const cv = $('timeline'), ctx = cv.getContext('2d');
const ROW_H = 110, LEFT = 8, AXIS = 52;  // AXIS: room for y-axis values

function draw() {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = ROWS.length * ROW_H;
  if (cv.width !== w * dpr || cv.height !== h * dpr) { cv.width = w * dpr; cv.height = h * dpr; cv.style.height = h + 'px'; }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.font = '10px system-ui';
  ROWS.forEach((r, i) => drawLabel(r, i * ROW_H, w));
  if (clockOffset !== null) {
    const win = +$('win').value, tEnd = performance.now() / 1000 + clockOffset, t0 = tEnd - win;
    const x = t => AXIS + (t - t0) / win * (w - AXIS - LEFT);
    ROWS.forEach((r, i) => drawRow(r, i * ROW_H, x, t0));
    drawMarkers(x, t0, h);
  }
  drawGaze();
  requestAnimationFrame(draw);
}

function drawLabel(r, y0, w) {
  ctx.fillStyle = '#7f95ab'; ctx.fillText(r.title, LEFT, y0 + 12);
  ctx.strokeStyle = '#1c2330'; ctx.beginPath(); ctx.moveTo(0, y0 + ROW_H - 0.5); ctx.lineTo(w, y0 + ROW_H - 0.5); ctx.stroke();
}

function tick(v, step) {  // value label with sensible precision
  const d = step >= 10 ? 0 : step >= 1 ? 1 : step >= 0.1 ? 2 : 3;
  return v.toFixed(d);
}
function drawAxis(lo, hi, y, w) {
  ctx.font = '10px system-ui'; ctx.textAlign = 'right';
  for (const v of [lo, (lo + hi) / 2, hi]) {
    ctx.strokeStyle = '#1c2330'; ctx.beginPath(); ctx.moveTo(AXIS, y(v)); ctx.lineTo(w - LEFT, y(v)); ctx.stroke();
    ctx.fillStyle = '#7f95ab'; ctx.fillText(tick(v, (hi - lo) / 2), AXIS - 4, y(v) + 3);
  }
  ctx.textAlign = 'left';
}

function drawRow(r, y0, x, t0) {
  const b = buf[r.stream]; if (!b || !b.t.length) return;
  const raw = (i, j) => (r.map ? r.map(b.v[i]) : r.ch.map(c => b.v[i][c]))[j];
  // display only: trailing average over `smooth` seconds (pupil is reported in 0.01 mm steps)
  const val = !r.smooth ? raw : (i, j) => {
    if (!Number.isFinite(raw(i, j))) return NaN;
    let sum = 0, n = 0;
    for (let k = i; k >= 0 && b.t[i] - b.t[k] < r.smooth; k--) { const v = raw(k, j); if (Number.isFinite(v)) { sum += v; n++; } }
    return sum / n;
  };
  const n = r.map ? 1 : r.ch.length;
  const vis = [];
  for (let i = 0; i < b.t.length; i++) if (b.t[i] >= t0) for (let j = 0; j < n; j++) {
    const v = val(i, j); if (Number.isFinite(v)) vis.push(v);
  }
  if (!vis.length) return;
  let lo, hi;
  if (r.range) [lo, hi] = r.range;
  else if (r.robust) {  // ignore the few extreme samples (e.g. at blink edges) when scaling
    vis.sort((a, c) => a - c);
    lo = vis[Math.floor(vis.length * 0.01)]; hi = vis[Math.ceil(vis.length * 0.99) - 1];
  } else { lo = Math.min(...vis); hi = Math.max(...vis); }
  if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
  const top = y0 + 18, span = ROW_H - 26, y = v => top + (hi - Math.min(hi, Math.max(lo, v))) / (hi - lo) * span;
  drawAxis(lo, hi, y, cv.clientWidth);
  if (r.bands && buf[r.bands.stream]) {  // shade where e.g. a fixation is detected
    const fb = buf[r.bands.stream];
    ctx.fillStyle = 'rgba(62,207,178,0.12)';
    for (let i = 1; i < fb.t.length; i++)
      if (fb.t[i] >= t0 && fb.v[i][r.bands.ch]) ctx.fillRect(x(fb.t[i - 1]), top, x(fb.t[i]) - x(fb.t[i - 1]) + 0.5, span);
  }
  for (let j = 0; j < n; j++) {
    ctx.strokeStyle = ctx.fillStyle = r.colors[j];
    ctx.lineWidth = 1.2; ctx.beginPath(); let pen = false, tPrev = -Infinity;
    for (let i = 0; i < b.t.length; i++) {
      if (b.t[i] < t0) continue;
      const v = val(i, j);
      // missing values and dropouts (e.g. blinks) stay visible as gaps
      if (!Number.isFinite(v) || (r.gap && b.t[i] - tPrev > r.gap)) pen = false;
      tPrev = b.t[i];
      if (!Number.isFinite(v)) continue;
      if (r.dots) { ctx.fillRect(x(b.t[i]) - 1.5, y(v) - 1.5, 3, 3); continue; }
      pen ? ctx.lineTo(x(b.t[i]), y(v)) : ctx.moveTo(x(b.t[i]), y(v)); pen = true;
    }
    ctx.stroke();
  }
}

function drawMarkers(x, t0, h) {
  for (const [s, b] of Object.entries(buf)) {
    if (!isMarkerStream(s)) continue;
    for (let i = 0; i < b.t.length; i++) {
      if (b.t[i] < t0) continue;
      const px = x(b.t[i]);
      ctx.strokeStyle = ctx.fillStyle = '#f5c142';
      ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, h); ctx.stroke();
      ctx.fillText(b.v[i][0], px + 3, 10);
    }
  }
}

// ── Gaze panel: last 2 s of gaze over the scene camera (or a blank frame without it) ──
const gc = $('gaze'), gctx = gc.getContext('2d');
function drawGaze() {
  const w = gc.clientWidth, h = gc.clientHeight, dpr = window.devicePixelRatio || 1;
  if (gc.width !== w * dpr || gc.height !== h * dpr) { gc.width = w * dpr; gc.height = h * dpr; }
  gctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  gctx.clearRect(0, 0, w, h);
  const b = buf.norad_tobii, fb = buf.norad_fixation;
  if (!b || !b.t.length || clockOffset === null) return;
  const tEnd = performance.now() / 1000 + clockOffset;
  let prev = null;
  for (let i = 0; i < b.t.length; i++) {
    const age = tEnd - b.t[i], gx = b.v[i][1], gy = b.v[i][2];
    if (age > 2 || !Number.isFinite(gx) || !Number.isFinite(gy)) { prev = null; continue; }
    const p = [gx * w, gy * h];
    if (prev) {
      gctx.strokeStyle = `rgba(62,207,178,${0.8 * (1 - age / 2)})`;
      gctx.lineWidth = 1.5; gctx.beginPath(); gctx.moveTo(...prev); gctx.lineTo(...p); gctx.stroke();
    }
    prev = p;
  }
  if (prev) {
    const fixating = fb && fb.v.length && fb.v[fb.v.length - 1][1];
    gctx.strokeStyle = gctx.fillStyle = '#3ecfb2'; gctx.lineWidth = 2;
    gctx.beginPath(); gctx.arc(prev[0], prev[1], 7, 0, 2 * Math.PI);
    fixating ? gctx.fill() : gctx.stroke();
  }
}

// ── Scene camera: fetch the newest frame, then the next (about 10 per second) ──
const sceneImg = $('scene');
function nextFrame() {
  fetch('/scene.jpg', { cache: 'no-store' })
    .then(r => r.status === 200 ? r.blob() : null)
    .then(blob => {
      if (blob) { const old = sceneImg.src; sceneImg.src = URL.createObjectURL(blob); if (old) URL.revokeObjectURL(old); }
      else sceneImg.removeAttribute('src');
    })
    .catch(() => {})
    .finally(() => setTimeout(nextFrame, 100));
}
nextFrame();

socket.emit('connect_devices', {});
requestAnimationFrame(draw);
