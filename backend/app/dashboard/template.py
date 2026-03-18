"""Embedded HTML/CSS/JS template for the operator dashboard.

Self-contained — no build step, no external dependencies.
BrightWheel-themed with the brand color palette.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Operator Dashboard — Sunshine Learning Center</title>
<style>
  :root {
    --blackout: #1E2549;
    --blueberry: #37458A;
    --blurple: #5463D6;
    --barney: #6476FF;
    --butterfly: #B1BAFF;
    --barnacle: #EEF1FF;
    --bubble: #F7F9FF;
    --sangria: #A40C31;
    --white: #FFFFFF;
    --green: #4CAF50;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
    background: var(--bubble);
    color: var(--blackout);
    line-height: 1.5;
  }
  header {
    background: var(--white);
    border-bottom: 1px solid var(--barnacle);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }
  header h1 { font-size: 18px; color: var(--blackout); }
  header h1 span { color: var(--blurple); font-weight: normal; }
  .refresh-btn {
    background: var(--barnacle);
    border: none;
    padding: 8px 16px;
    border-radius: 8px;
    color: var(--blueberry);
    cursor: pointer;
    font-size: 13px;
  }
  .refresh-btn:hover { background: var(--butterfly); }

  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

  /* KPI Cards */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .kpi-card {
    background: var(--white);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--barnacle);
  }
  .kpi-card .label { font-size: 12px; color: var(--blueberry); text-transform: uppercase; letter-spacing: 0.5px; }
  .kpi-card .value { font-size: 28px; font-weight: 700; color: var(--blackout); margin-top: 4px; }
  .kpi-card .value.warning { color: var(--sangria); }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
    border-bottom: 2px solid var(--barnacle);
    padding-bottom: 0;
  }
  .tab {
    padding: 10px 20px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 14px;
    color: var(--blueberry);
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s;
  }
  .tab:hover { color: var(--blurple); }
  .tab.active { color: var(--blurple); border-bottom-color: var(--blurple); font-weight: 600; }

  /* Panels */
  .panel { display: none; }
  .panel.active { display: block; }

  /* Table */
  table { width: 100%; border-collapse: collapse; background: var(--white); border-radius: 12px; overflow: hidden; border: 1px solid var(--barnacle); }
  th { background: var(--barnacle); padding: 12px 16px; text-align: left; font-size: 12px; color: var(--blueberry); text-transform: uppercase; letter-spacing: 0.5px; }
  td { padding: 12px 16px; border-top: 1px solid var(--barnacle); font-size: 14px; }
  tr:hover td { background: var(--bubble); }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge-transfer { background: #fecaca; color: var(--sangria); }
  .badge-ok { background: #d1fae5; color: #065f46; }
  .badge-pending { background: #fef3c7; color: #92400e; }

  /* FAQ Form */
  .form-group { margin-bottom: 12px; }
  .form-group label { display: block; font-size: 12px; color: var(--blueberry); margin-bottom: 4px; }
  .form-group input, .form-group textarea {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--barnacle);
    border-radius: 8px;
    font-size: 14px;
    background: var(--bubble);
  }
  .form-group textarea { resize: vertical; min-height: 60px; }
  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    font-weight: 600;
  }
  .btn-primary { background: var(--blurple); color: white; }
  .btn-primary:hover { background: var(--barney); }
  .btn-danger { background: var(--sangria); color: white; }
  .btn-danger:hover { opacity: 0.9; }
  .btn-sm { padding: 4px 10px; font-size: 12px; }

  /* Session detail modal */
  .modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(30,37,73,0.5);
    z-index: 100;
    justify-content: center;
    align-items: center;
  }
  .modal-overlay.open { display: flex; }
  .modal {
    background: var(--white);
    border-radius: 16px;
    padding: 24px;
    max-width: 700px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
  }
  .modal h2 { margin-bottom: 16px; font-size: 16px; }
  .modal .close-btn { float: right; background: none; border: none; font-size: 20px; cursor: pointer; color: var(--blueberry); }
  .msg-bubble {
    margin: 8px 0;
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 14px;
    max-width: 80%;
  }
  .msg-user { background: var(--blurple); color: white; margin-left: auto; border-bottom-right-radius: 4px; }
  .msg-assistant { background: var(--barnacle); color: var(--blackout); border-bottom-left-radius: 4px; }
  .msg-label { font-size: 11px; color: var(--blueberry); margin-bottom: 2px; }

  /* Rating stars */
  .stars { color: #f59e0b; letter-spacing: 2px; }
  .stars-dim { color: #d1d5db; letter-spacing: 2px; }

  /* Rating distribution bar */
  .rating-bar-row { display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: 13px; }
  .rating-bar-label { width: 20px; text-align: right; color: var(--blueberry); }
  .rating-bar-track { flex: 1; height: 20px; background: var(--barnacle); border-radius: 4px; overflow: hidden; }
  .rating-bar-fill { height: 100%; background: var(--blurple); border-radius: 4px; transition: width 0.3s; }
  .rating-bar-count { width: 30px; font-size: 12px; color: var(--blueberry); }

  /* Filters */
  .filters { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
  .filters select, .filters input {
    padding: 6px 10px;
    border: 1px solid var(--barnacle);
    border-radius: 8px;
    font-size: 13px;
    background: var(--white);
  }
  .filters label { font-size: 12px; color: var(--blueberry); }

  /* Alert card */
  .alert-card {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
  }
  .alert-card .alert-rating { font-weight: 700; color: var(--sangria); }
</style>
</head>
<body>

<header>
  <h1>🦉 Operator Dashboard <span>— Sunshine Learning Center</span></h1>
  <button class="refresh-btn" onclick="loadAll()">↻ Refresh</button>
</header>

<div class="container">
  <div class="kpi-grid" id="kpi-grid"></div>

  <div class="tabs">
    <button class="tab active" data-tab="sessions">Sessions</button>
    <button class="tab" data-tab="analytics">Analytics</button>
    <button class="tab" data-tab="struggles">Struggles</button>
    <button class="tab" data-tab="faq">FAQ Overrides</button>
    <button class="tab" data-tab="tours">Tour Requests</button>
  </div>

  <div id="sessions" class="panel active"></div>
  <div id="analytics" class="panel"></div>
  <div id="struggles" class="panel"></div>
  <div id="faq" class="panel"></div>
  <div id="tours" class="panel"></div>
</div>

<div class="modal-overlay" id="session-modal">
  <div class="modal">
    <button class="close-btn" onclick="closeModal()">&times;</button>
    <h2 id="modal-title">Session Detail</h2>
    <div id="modal-body"></div>
  </div>
</div>

<script>
const API = '';  // Same origin

// ── Tab switching ──
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

// ── Load all data ──
async function loadAll() {
  await Promise.all([loadStats(), loadSessions(), loadStruggles(), loadFAQ(), loadTours(), loadAnalytics()]);
}

function renderStars(rating) {
  const full = Math.round(rating);
  return '<span class="stars">' + '★'.repeat(full) + '</span><span class="stars-dim">' + '★'.repeat(5 - full) + '</span>';
}

async function loadStats() {
  const data = await fetch(API + '/api/stats').then(r => r.json());
  const ratingDisplay = data.rating_count > 0
    ? `${renderStars(data.avg_rating)} ${data.avg_rating}`
    : '<span style="color:#888">No ratings</span>';
  document.getElementById('kpi-grid').innerHTML = `
    <div class="kpi-card"><div class="label">Total Sessions</div><div class="value">${data.total_sessions}</div></div>
    <div class="kpi-card"><div class="label">Total Messages</div><div class="value">${data.total_messages}</div></div>
    <div class="kpi-card"><div class="label">Avg Rating (${data.rating_count})</div><div class="value">${ratingDisplay}</div></div>
    <div class="kpi-card"><div class="label">Transfer Rate</div><div class="value ${data.transfer_rate > 20 ? 'warning' : ''}">${data.transfer_rate}%</div></div>
  `;
}

async function loadSessions() {
  // Build query params from filters
  const params = new URLSearchParams();
  const minRating = document.getElementById('filter-min-rating')?.value;
  const transferred = document.getElementById('filter-transferred')?.checked;
  if (minRating && minRating !== '') params.set('min_rating', minRating);
  if (transferred) params.set('transferred_only', 'true');
  const qs = params.toString() ? '?' + params.toString() : '';

  const data = await fetch(API + '/api/sessions' + qs).then(r => r.json());
  const rows = data.map(s => {
    const ratingHtml = s.rating ? renderStars(s.rating) : '<span style="color:#ccc">—</span>';
    return `
    <tr onclick="openSession('${s.id}')" style="cursor:pointer">
      <td>${new Date(s.started_at).toLocaleString()}</td>
      <td>${s.input_mode || 'text'}</td>
      <td>${ratingHtml}</td>
      <td>${s.security_code_used ? '🔐 ' + s.security_code_used : '—'}</td>
      <td>${s.transferred_to_human ? '<span class="badge badge-transfer">Transferred</span>' : '<span class="badge badge-ok">OK</span>'}</td>
    </tr>
  `}).join('');
  document.getElementById('sessions').innerHTML = `
    <div class="filters">
      <label>Min rating:
        <select id="filter-min-rating" onchange="loadSessions()">
          <option value="">All</option>
          <option value="1" ${minRating==='1'?'selected':''}>1+</option>
          <option value="2" ${minRating==='2'?'selected':''}>2+</option>
          <option value="3" ${minRating==='3'?'selected':''}>3+</option>
          <option value="4" ${minRating==='4'?'selected':''}>4+</option>
          <option value="5" ${minRating==='5'?'selected':''}>5</option>
        </select>
      </label>
      <label>
        <input type="checkbox" id="filter-transferred" onchange="loadSessions()" ${transferred?'checked':''}> Transferred only
      </label>
    </div>
    <table>
      <thead><tr><th>Started</th><th>Mode</th><th>Rating</th><th>Code</th><th>Status</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5" style="text-align:center;color:#888">No sessions yet</td></tr>'}</tbody>
    </table>
  `;
}

async function loadStruggles() {
  const data = await fetch(API + '/api/struggles').then(r => r.json());
  const rows = data.map(s => `
    <tr onclick="openSession('${s.id}')" style="cursor:pointer">
      <td>${new Date(s.started_at).toLocaleString()}</td>
      <td>${s.transfer_reason || 'Unknown'}</td>
      <td>${s.message_count} msgs</td>
    </tr>
  `).join('');
  document.getElementById('struggles').innerHTML = data.length === 0
    ? '<p style="text-align:center;color:#888;padding:40px">No struggles detected yet. Great job!</p>'
    : `<table><thead><tr><th>When</th><th>Reason</th><th>Messages</th></tr></thead><tbody>${rows}</tbody></table>`;
}

async function loadFAQ() {
  const data = await fetch(API + '/api/faq-overrides').then(r => r.json());
  const rows = data.map(o => `
    <tr>
      <td>${o.question_pattern}</td>
      <td>${o.answer}</td>
      <td>${o.created_by}</td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="deleteFAQ(${o.id})">Delete</button>
      </td>
    </tr>
  `).join('');
  document.getElementById('faq').innerHTML = `
    <div style="margin-bottom:16px;background:white;padding:16px;border-radius:12px;border:1px solid var(--barnacle)">
      <h3 style="font-size:14px;margin-bottom:12px">Add New Override</h3>
      <div class="form-group"><label>Question Pattern</label><input id="faq-q" placeholder="What are your hours?"></div>
      <div class="form-group"><label>Answer</label><textarea id="faq-a" placeholder="We are open 7 AM to 5:30 PM..."></textarea></div>
      <button class="btn btn-primary" onclick="addFAQ()">Add Override</button>
    </div>
    <table>
      <thead><tr><th>Question</th><th>Answer</th><th>Created By</th><th>Actions</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" style="text-align:center;color:#888">No overrides yet</td></tr>'}</tbody>
    </table>
  `;
}

async function loadTours() {
  const data = await fetch(API + '/api/tour-requests').then(r => r.json());
  const rows = data.map(t => `
    <tr>
      <td>${t.parent_name}</td>
      <td>${t.parent_phone}</td>
      <td>${t.parent_email || '—'}</td>
      <td>${t.preferred_date}</td>
      <td><span class="badge badge-pending">${t.status}</span></td>
      <td>${new Date(t.created_at).toLocaleString()}</td>
    </tr>
  `).join('');
  document.getElementById('tours').innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Preferred Date</th><th>Status</th><th>Submitted</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6" style="text-align:center;color:#888">No tour requests yet</td></tr>'}</tbody>
    </table>
  `;
}

// ── Session detail modal ──
async function openSession(id) {
  const data = await fetch(API + '/api/sessions/' + id).then(r => r.json());
  document.getElementById('modal-title').textContent = 'Session: ' + id.substring(0, 8) + '...';
  const msgs = (data.messages || []).map(m => `
    <div style="display:flex;flex-direction:column;${m.role === 'user' ? 'align-items:flex-end' : 'align-items:flex-start'}">
      <div class="msg-label">${m.role === 'user' ? 'Parent' : 'Ms. Olivia'}${m.tool_used ? ' (used: ' + m.tool_used + ')' : ''}</div>
      <div class="msg-bubble ${m.role === 'user' ? 'msg-user' : 'msg-assistant'}">${m.content}</div>
    </div>
  `).join('');
  document.getElementById('modal-body').innerHTML = msgs || '<p style="color:#888">No messages in this session.</p>';
  document.getElementById('session-modal').classList.add('open');
}

function closeModal() {
  document.getElementById('session-modal').classList.remove('open');
}

document.getElementById('session-modal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeModal();
});

// ── FAQ CRUD ──
async function addFAQ() {
  const q = document.getElementById('faq-q').value.trim();
  const a = document.getElementById('faq-a').value.trim();
  if (!q || !a) return;
  await fetch(API + '/api/faq-overrides', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question_pattern: q, answer: a})
  });
  loadFAQ();
}

async function deleteFAQ(id) {
  if (!confirm('Delete this FAQ override?')) return;
  await fetch(API + '/api/faq-overrides/' + id, {method: 'DELETE'});
  loadFAQ();
}

// ── Analytics panel ──
async function loadAnalytics() {
  const [dist, citations, lowRating] = await Promise.all([
    fetch(API + '/api/rating-distribution').then(r => r.json()),
    fetch(API + '/api/citation-frequency').then(r => r.json()),
    fetch(API + '/api/low-rating-sessions').then(r => r.json()),
  ]);

  // Rating distribution
  const maxCount = Math.max(...dist.map(d => d.count), 1);
  const distBars = [5,4,3,2,1].map(rating => {
    const entry = dist.find(d => d.rating === rating);
    const count = entry ? entry.count : 0;
    const pct = (count / maxCount * 100).toFixed(0);
    return `<div class="rating-bar-row">
      <div class="rating-bar-label">${rating}★</div>
      <div class="rating-bar-track"><div class="rating-bar-fill" style="width:${pct}%"></div></div>
      <div class="rating-bar-count">${count}</div>
    </div>`;
  }).join('');

  // Citation frequency
  const citationRows = citations.slice(0, 10).map(c => `
    <tr><td>Page ${c.page}</td><td>${c.count} citations</td></tr>
  `).join('');

  // Low rating alerts
  const alerts = lowRating.map(s => `
    <div class="alert-card">
      <div><span class="alert-rating">${s.rating}★</span> — ${new Date(s.started_at).toLocaleString()}</div>
      ${s.rating_feedback ? `<div style="margin-top:4px;font-size:13px;color:#555">"${s.rating_feedback}"</div>` : ''}
      <button class="btn btn-sm" style="margin-top:8px" onclick="openSession('${s.id}')">View session</button>
    </div>
  `).join('');

  document.getElementById('analytics').innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
      <div>
        <h3 style="font-size:14px;margin-bottom:12px;color:var(--blueberry)">Rating Distribution</h3>
        <div style="background:white;padding:16px;border-radius:12px;border:1px solid var(--barnacle)">
          ${dist.length > 0 ? distBars : '<p style="color:#888;text-align:center">No ratings yet</p>'}
        </div>
      </div>
      <div>
        <h3 style="font-size:14px;margin-bottom:12px;color:var(--blueberry)">Most Cited Pages</h3>
        <table>
          <thead><tr><th>Page</th><th>Citations</th></tr></thead>
          <tbody>${citationRows || '<tr><td colspan="2" style="text-align:center;color:#888">No citations yet</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    <div style="margin-top:24px">
      <h3 style="font-size:14px;margin-bottom:12px;color:var(--sangria)">Low Rating Sessions (≤2★)</h3>
      ${alerts || '<p style="color:#888">No low-rating sessions. Great job!</p>'}
    </div>
  `;
}

// ── Auto-refresh ──
loadAll();
setInterval(loadAll, 30000);
</script>
</body>
</html>"""
