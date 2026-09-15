/**
 * GridGuard — Dashboard Application
 * Manages WebSocket, real-time updates, approval modal, incident reports,
 * attack injection, node sidebar, timeline filters, dark/light mode, monitoring.
 */

'use strict';

// ── Config ───────────────────────────────────────────────────────────────────
const WS_RECONNECT_DELAY = 3000;
const PHOENIX_POLL_INTERVAL = 15000;
const REPORT_POLL_INTERVAL = 8000;
const HISTORY_POLL_INTERVAL = 5000;
const QUOTA_DAILY_LIMIT = 1000;
const CALLS_PER_ATTACK = 8; // estimated API calls per pipeline run

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  ws: null,
  wsConnected: false,
  nodes: {},
  timelineEvents: [],
  reports: [],
  incidents: [],
  pendingApprovals: {},
  approvalCountdownTimer: null,
  currentApprovalId: null,
  currentReport: null,
  lastTelemetry: null,
  timelineFilter: 'all',
  // Monitoring
  startTime: Date.now(),
  quotaUsed: 0,
  pipelineRunning: false,
  pipelineStartTime: null,
  pipelineTimerInterval: null,
  incidentCountToday: 0,
  // Theme
  darkMode: true,
  // Node sidebar
  selectedNode: null,
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadThemePreference();
  initNodes();
  connectWebSocket();
  startClock();
  startUptimeTicker();
  pollPhoenixStats();
  pollReports();
  pollIncidentHistory();
  setInterval(pollPhoenixStats, PHOENIX_POLL_INTERVAL);
  setInterval(pollReports, REPORT_POLL_INTERVAL);
  setInterval(pollIncidentHistory, HISTORY_POLL_INTERVAL);
});

// ── Theme ─────────────────────────────────────────────────────────────────────
function loadThemePreference() {
  const saved = localStorage.getItem('gridguard-theme');
  if (saved === 'light') {
    state.darkMode = false;
    document.body.classList.add('light-mode');
    $('theme-toggle').textContent = '☀️';
  }
}

function toggleTheme() {
  state.darkMode = !state.darkMode;
  document.body.classList.toggle('light-mode', !state.darkMode);
  $('theme-toggle').textContent = state.darkMode ? '🌙' : '☀️';
  localStorage.setItem('gridguard-theme', state.darkMode ? 'dark' : 'light');
}

// ── Monitoring Bar ────────────────────────────────────────────────────────────
function startUptimeTicker() {
  setInterval(updateMonitoringBar, 5000);
  updateMonitoringBar();
}

function updateMonitoringBar() {
  // Uptime
  const uptimeSecs = Math.floor((Date.now() - state.startTime) / 1000);
  const uptimeStr = uptimeSecs < 3600
    ? `${Math.floor(uptimeSecs / 60)}m ${uptimeSecs % 60}s`
    : `${Math.floor(uptimeSecs / 3600)}h ${Math.floor((uptimeSecs % 3600) / 60)}m`;
  $('mon-uptime-val').textContent = uptimeStr;

  // Quota
  const quotaEl = $('mon-quota');
  const quotaVal = $('mon-quota-val');
  const quotaBar = $('mon-quota-bar');
  quotaVal.textContent = `${state.quotaUsed} / ${QUOTA_DAILY_LIMIT}`;
  const pct = state.quotaUsed / QUOTA_DAILY_LIMIT;
  quotaEl.className = `monitor-item ${pct > 0.8 ? 'danger' : pct > 0.5 ? 'warn' : 'good'}`;
  if (quotaBar) {
    quotaBar.style.width = `${Math.min(pct * 100, 100)}%`;
    quotaBar.style.background = pct > 0.8 ? 'var(--red)' : pct > 0.5 ? 'var(--yellow)' : 'var(--green)';
  }

  // Pipeline status (updated by pipeline events)
  if (!state.pipelineRunning) {
    $('mon-pipeline-val').textContent = 'Idle';
    $('mon-pipeline').className = 'monitor-item';
  }

  // WS status
  $('mon-ws-val').textContent = state.wsConnected ? 'Connected' : 'Reconnecting';
  $('mon-ws').className = `monitor-item ${state.wsConnected ? 'good' : 'warn'}`;
}

function trackPipelineStart() {
  state.pipelineRunning = true;
  state.pipelineStartTime = Date.now();
  state.quotaUsed += CALLS_PER_ATTACK;
  state.incidentCountToday++;
  $('mon-incidents-val').textContent = `${state.incidentCountToday} today`;
  $('mon-pipeline').className = 'monitor-item warn';

  clearInterval(state.pipelineTimerInterval);
  state.pipelineTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - state.pipelineStartTime) / 1000);
    $('mon-pipeline-val').textContent = `Running ${elapsed}s`;
    if (elapsed > 120) {
      $('mon-pipeline').className = 'monitor-item danger';
    }
  }, 1000);
}

function trackPipelineEnd() {
  state.pipelineRunning = false;
  clearInterval(state.pipelineTimerInterval);
  $('mon-pipeline-val').textContent = 'Idle';
  $('mon-pipeline').className = 'monitor-item';
}

// ── Grid Node Initialization ─────────────────────────────────────────────────
function initNodes() {
  const map = $('grid-map');
  map.innerHTML = '';
  for (let i = 1; i <= 12; i++) {
    const id = `SUBSTATION_${String(i).padStart(3, '0')}`;
    const node = document.createElement('div');
    node.className = 'grid-node node-normal';
    node.id = `node-${id}`;
    node.title = id;
    node.innerHTML = `
      <span class="node-icon">⚡</span>
      <span class="node-id">S${String(i).padStart(3, '0')}</span>
    `;
    node.addEventListener('click', () => showNodeSidebar(id));
    map.appendChild(node);
    state.nodes[id] = 'NORMAL';
  }
}

function updateNodes(nodeStates) {
  if (!nodeStates) return;
  let hasThreats = false;

  for (const [id, status] of Object.entries(nodeStates)) {
    const el = $(`node-${id}`);
    if (!el) continue;
    state.nodes[id] = status;
    el.className = 'grid-node';
    el.querySelector('.node-icon').textContent = nodeIcon(status);
    switch (status) {
      case 'THREAT': el.classList.add('node-threat'); hasThreats = true; break;
      case 'INVESTIGATING': el.classList.add('node-investigating'); break;
      case 'RESOLVED': el.classList.add('node-resolved'); break;
      default: el.classList.add('node-normal');
    }
    // Refresh sidebar if open
    if (state.selectedNode === id) refreshNodeSidebar(id);
  }

  const badge = $('map-badge');
  if (hasThreats) {
    badge.textContent = '⚠ THREAT DETECTED';
    badge.classList.add('badge-alert');
  } else {
    badge.textContent = 'ALL NOMINAL';
    badge.classList.remove('badge-alert');
  }

  const threatCount = Object.values(nodeStates).filter(s => s === 'THREAT').length;
  if (threatCount > 0) {
    $('pill-threats-val').textContent = `${threatCount} Active Threat${threatCount > 1 ? 's' : ''}`;
    $('threat-dot').classList.remove('hidden');
  } else {
    $('pill-threats-val').textContent = 'No Active Threats';
    $('threat-dot').classList.add('hidden');
  }
}

function nodeIcon(status) {
  return { THREAT: '🔴', INVESTIGATING: '🟡', RESOLVED: '🔵', NORMAL: '⚡' }[status] || '⚡';
}

// ── Node Sidebar ──────────────────────────────────────────────────────────────
function showNodeSidebar(id) {
  state.selectedNode = id;
  $('node-sidebar').classList.add('open');
  $('node-sidebar-backdrop').classList.add('open');
  refreshNodeSidebar(id);
}

function refreshNodeSidebar(id) {
  const status = state.nodes[id] || 'NORMAL';
  const telem = state.lastTelemetry && state.lastTelemetry.node_id === id ? state.lastTelemetry : null;

  $('node-sidebar-title').textContent = id;

  const statusClasses = {
    NORMAL: 'status-normal', THREAT: 'status-threat',
    INVESTIGATING: 'status-investigating', RESOLVED: 'status-resolved'
  };
  const statusLabels = {
    NORMAL: '✅ Normal', THREAT: '🔴 Threat Active',
    INVESTIGATING: '🟡 Investigating', RESOLVED: '🔵 Resolved'
  };

  const nodeEvents = state.timelineEvents
    .filter(e => e.incident_id &&
      state.timelineEvents.some(t => t.incident_id === e.incident_id && t.agent !== 'gridguard_pipeline'))
    .slice(0, 5);

  $('node-sidebar-body').innerHTML = `
    <div>
      <span class="node-status-badge ${statusClasses[status] || 'status-normal'}">
        ${statusLabels[status] || status}
      </span>
    </div>

    ${telem ? `
    <div>
      <div class="node-section-title">Live Telemetry</div>
      <div class="node-stat-grid">
        <div class="node-stat">
          <div class="node-stat-label">Voltage</div>
          <div class="node-stat-value ${telem.voltage && (telem.voltage < 218 || telem.voltage > 242) ? 'anomaly' : 'normal'}">
            ${telem.voltage ? telem.voltage.toFixed(1) : '—'}V
          </div>
        </div>
        <div class="node-stat">
          <div class="node-stat-label">Frequency</div>
          <div class="node-stat-value ${telem.frequency && Math.abs(telem.frequency - 50) > 0.5 ? 'anomaly' : 'normal'}">
            ${telem.frequency ? telem.frequency.toFixed(2) : '—'}Hz
          </div>
        </div>
        <div class="node-stat">
          <div class="node-stat-label">Current</div>
          <div class="node-stat-value">${telem.current ? telem.current.toFixed(1) : '—'}A</div>
        </div>
        <div class="node-stat">
          <div class="node-stat-label">Grid Status</div>
          <div class="node-stat-value ${telem.status === 'ANOMALY' ? 'anomaly' : 'normal'}">${telem.status || '—'}</div>
        </div>
      </div>
    </div>
    ` : `<div style="color:var(--text-muted);font-size:11px">No telemetry — this node has not been active</div>`}

    <div>
      <div class="node-section-title">Recent Events</div>
      ${nodeEvents.length ? nodeEvents.map(e => `
        <div class="node-event-item">
          <div class="node-event-time">${formatTime(e.timestamp)}</div>
          <div class="node-event-action">${escHtml(formatAction(e.action))}</div>
        </div>
      `).join('') : `<div style="color:var(--text-muted);font-size:11px">No recent events</div>`}
    </div>
  `;
}

function closeNodeSidebar() {
  $('node-sidebar').classList.remove('open');
  $('node-sidebar-backdrop').classList.remove('open');
  state.selectedNode = null;
}

// ── Timeline Filter ───────────────────────────────────────────────────────────
function setTimelineFilter(filter) {
  state.timelineFilter = filter;

  // Update button states
  const filterMap = {
    'all': 'filter-all',
    'detection_agent': 'filter-detection',
    'investigation_agent': 'filter-investigation',
    'response_agent': 'filter-response',
    'CRITICAL': 'filter-critical',
    'gridguard_pipeline': 'filter-pipeline',
  };

  // Reset all buttons
  Object.values(filterMap).forEach(id => {
    const btn = $(id);
    if (btn) btn.className = 'filter-btn';
  });

  // Activate selected
  const activeId = filterMap[filter];
  if (activeId && $(activeId)) {
    const activeClasses = {
      'all': 'active', 'detection_agent': 'active-blue',
      'investigation_agent': 'active-blue', 'response_agent': 'active-orange',
      'CRITICAL': 'active-red', 'gridguard_pipeline': 'active-yellow',
    };
    $(activeId).className = `filter-btn ${activeClasses[filter] || 'active'}`;
  }

  // Re-render timeline with filter
  rerenderTimeline();
}

function filterEvent(ev) {
  if (state.timelineFilter === 'all') return true;
  if (state.timelineFilter === 'CRITICAL') return ev.severity === 'CRITICAL';
  return ev.agent === state.timelineFilter;
}

function rerenderTimeline() {
  const feed = $('timeline-feed');
  feed.innerHTML = '';

  const filtered = state.timelineEvents.filter(filterEvent);

  if (filtered.length === 0) {
    feed.innerHTML = `
      <div class="timeline-empty">
        <div class="empty-icon">🔍</div>
        <div>No events match this filter</div>
      </div>`;
    return;
  }

  filtered.forEach(ev => {
    const entry = buildTimelineEntry(ev);
    feed.appendChild(entry);
  });
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWebSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/threats`;
  state.ws = new WebSocket(url);

  state.ws.onopen = () => {
    state.wsConnected = true;
    $('mon-ws-val').textContent = 'Connected';
    $('mon-ws').className = 'monitor-item good';
  };

  state.ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      handleDashboardUpdate(data);
    } catch (err) {
      console.warn('[GridGuard] WS parse error:', err);
    }
  };

  state.ws.onclose = () => {
    state.wsConnected = false;
    $('mon-ws-val').textContent = 'Reconnecting';
    $('mon-ws').className = 'monitor-item warn';
    setTimeout(connectWebSocket, WS_RECONNECT_DELAY);
  };

  state.ws.onerror = () => state.ws.close();
}

function handleDashboardUpdate(data) {
  if (data.node_states) updateNodes(data.node_states);

  if (data.recent_threats && data.recent_threats.length > 0) {
    const latest = data.recent_threats[data.recent_threats.length - 1];
    updateTelemetry(latest);
  }

  if (data.timeline) updateTimeline(data.timeline);

  if (data.pending_approvals && data.pending_approvals.length > 0) {
    const approval = data.pending_approvals[0];
    if (approval.incident_id !== state.currentApprovalId) {
      showApprovalModal(approval);
    }
  } else if (state.currentApprovalId) {
    closeApprovalModal();
  }
}

// ── Telemetry Display ─────────────────────────────────────────────────────────
function updateTelemetry(reading) {
  if (!reading) return;
  state.lastTelemetry = reading;
  const isAnomaly = reading.status === 'ANOMALY';

  $('telem-voltage').textContent = reading.voltage ? `${reading.voltage.toFixed(1)} V` : '— V';
  $('telem-frequency').textContent = reading.frequency ? `${reading.frequency.toFixed(2)} Hz` : '— Hz';
  $('telem-node').textContent = reading.node_id || '—';
  $('telem-status').textContent = reading.status || 'NORMAL';

  $('telem-voltage').className = 'telem-value ' + (isAnomaly ? 'telem-anomaly' : 'telem-normal');
  $('telem-status').className = 'telem-value ' + (isAnomaly ? 'telem-anomaly' : 'telem-normal');

  // Refresh sidebar if showing this node
  if (state.selectedNode === reading.node_id) refreshNodeSidebar(reading.node_id);
}

// ── Timeline ──────────────────────────────────────────────────────────────────
function updateTimeline(events) {
  if (!events || events.length === 0) return;

  const existingIds = new Set(state.timelineEvents.map(e => e.id));
  const newEvents = events.filter(e => !existingIds.has(e.id));
  if (newEvents.length === 0) return;

  state.timelineEvents = events;

  // Track pipeline state for monitoring
  newEvents.forEach(ev => {
    if (ev.action === 'pipeline_started') trackPipelineStart();
    if (ev.action === 'pipeline_completed' || ev.action === 'pipeline_error') trackPipelineEnd();
  });

  const feed = $('timeline-feed');
  const empty = feed.querySelector('.timeline-empty');
  if (empty) empty.remove();

  // Only render events matching current filter
  newEvents.filter(filterEvent).forEach(ev => {
    const entry = buildTimelineEntry(ev);
    feed.insertBefore(entry, feed.firstChild);
  });

  $('timeline-count').textContent = `${events.length} event${events.length !== 1 ? 's' : ''}`;

  while (feed.children.length > 80) feed.removeChild(feed.lastChild);
}

function buildTimelineEntry(ev) {
  const div = document.createElement('div');
  div.className = `timeline-entry entry-sev-${ev.severity || 'INFO'}`;
  div.id = `entry-${ev.id}`;

  const icon = agentIcon(ev.agent, ev.severity);
  const time = formatTime(ev.timestamp);
  const action = formatAction(ev.action);
  const outcomeClass = ev.outcome ? `outcome-${ev.outcome.toLowerCase()}` : '';
  const conf = ev.confidence != null ? `conf: ${(ev.confidence * 100).toFixed(0)}%` : '';

  // Show full reasoning with expand toggle
  const reasoning = ev.reasoning || '';
  const shortReason = reasoning.substring(0, 160);
  const hasMore = reasoning.length > 160;

  div.innerHTML = `
    <span class="entry-icon">${icon}</span>
    <div class="entry-body">
      <div class="entry-top">
        <span class="entry-agent">${escHtml(ev.agent || '—')}</span>
        <span class="entry-time">${time}</span>
      </div>
      <div class="entry-action">${escHtml(action)}</div>
      <div class="entry-reason" id="reason-${ev.id}">${escHtml(shortReason)}${hasMore ? '…' : ''}</div>
      ${hasMore ? `<span class="entry-expand" onclick="toggleReason('${ev.id}', ${JSON.stringify(reasoning).replace(/'/g, "\\'")})" style="font-size:10px;color:var(--accent-cyan);cursor:pointer">▾ more</span>` : ''}
      <span class="entry-confidence">${conf}</span>
      ${ev.outcome ? `<span class="entry-outcome ${outcomeClass}">${escHtml(ev.outcome)}</span>` : ''}
    </div>
  `;
  return div;
}

function toggleReason(id, fullText) {
  const el = $(`reason-${id}`);
  const btn = el.nextElementSibling;
  if (!el || !btn) return;
  if (el.dataset.expanded === 'true') {
    el.textContent = fullText.substring(0, 160) + '…';
    btn.textContent = '▾ more';
    el.dataset.expanded = 'false';
  } else {
    el.textContent = fullText;
    btn.textContent = '▴ less';
    el.dataset.expanded = 'true';
  }
}

function agentIcon(agent, severity) {
  if (severity === 'CRITICAL') return '🚨';
  return ({
    detection_agent: '🔍',
    investigation_agent: '🔬',
    response_agent: '⚡',
    operator: '👤',
    gridguard_pipeline: '🤖',
    system: '⚙️',
  })[agent] || '•';
}

function formatAction(action) {
  if (!action) return '—';
  return action
    .replace(/_/g, ' ')
    .replace(/tool call:/i, '→ ')
    .replace(/tool result:/i, '← ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

// ── Incident History ──────────────────────────────────────────────────────────
async function pollIncidentHistory() {
  try {
    const res = await fetch('/api/incidents');
    if (!res.ok) return;
    const data = await res.json();
    renderIncidentHistory(data.incidents || []);
  } catch (e) { /* silent */ }
}

function renderIncidentHistory(incidents) {
  state.incidents = incidents;
  const list = $('incident-history-list');
  $('history-count').textContent = `${incidents.length} incident${incidents.length !== 1 ? 's' : ''}`;

  if (incidents.length === 0) {
    list.innerHTML = `
      <div class="timeline-empty" style="padding:20px">
        <div class="empty-icon">🗂</div><div>No incidents yet</div>
      </div>`;
    return;
  }

  list.innerHTML = '';
  incidents.slice().reverse().forEach(inc => {
    const row = document.createElement('div');
    row.className = 'incident-row';

    const dotClass = {
      executed: 'inc-executed', escalated: 'inc-escalated',
      error: 'inc-error', investigating: 'inc-investigating'
    }[inc.status] || 'inc-investigating';

    row.innerHTML = `
      <div class="incident-dot ${dotClass}"></div>
      <span class="incident-id">${escHtml(inc.incident_id || '—')}</span>
      <span class="incident-type">${escHtml((inc.attack_type || '').replace(/_/g, ' '))}</span>
      <span class="incident-status">${escHtml(inc.status || '—')}</span>
      <span class="incident-time">${formatTime(inc.started_at)}</span>
    `;
    list.appendChild(row);
  });
}

// ── Human Approval Modal ──────────────────────────────────────────────────────
function showApprovalModal(approval) {
  state.currentApprovalId = approval.incident_id;

  $('modal-incident-id').textContent = approval.incident_id || '—';
  $('modal-classification').textContent = approval.classification || '—';
  $('modal-summary').textContent = approval.summary || '—';
  $('modal-reasoning').textContent = approval.ai_reasoning || '—';
  $('modal-playbook').textContent = (approval.recommended_playbook || '—').toUpperCase();

  const mitreEl = $('modal-mitre');
  const techniques = approval.mitre_techniques || [];
  mitreEl.innerHTML = techniques.length
    ? techniques.map(t => `<div>${escHtml(t.technique_id || '')} — ${escHtml(t.name || '')}</div>`).join('')
    : '—';

  const cvesEl = $('modal-cves');
  const cves = approval.cves || [];
  cvesEl.innerHTML = cves.length
    ? cves.map(c => `<div>${escHtml(c.id || '')} (CVSS: ${c.cvss_score || '?'})</div>`).join('')
    : '—';

  $('approval-overlay').classList.remove('hidden');
  startApprovalCountdown(approval.timeout_seconds || 120);
}

function startApprovalCountdown(seconds) {
  clearInterval(state.approvalCountdownTimer);
  let remaining = seconds;
  $('approval-countdown').textContent = `${remaining}s`;

  state.approvalCountdownTimer = setInterval(() => {
    remaining--;
    $('approval-countdown').textContent = `${remaining}s`;
    if (remaining <= 0) {
      clearInterval(state.approvalCountdownTimer);
      submitApproval('escalated');
    }
  }, 1000);
}

async function submitApproval(result) {
  const id = state.currentApprovalId;
  if (!id) return;
  clearInterval(state.approvalCountdownTimer);
  try {
    const url = result === 'escalated'
      ? `/api/escalate/${encodeURIComponent(id)}`
      : `/api/approve/${encodeURIComponent(id)}?approved=${result === 'approved'}`;
    await fetch(url, { method: 'POST' });
  } catch (e) {
    console.warn('[GridGuard] Approval submit error:', e);
  }
  closeApprovalModal();
}

function closeApprovalModal() {
  $('approval-overlay').classList.add('hidden');
  state.currentApprovalId = null;
  clearInterval(state.approvalCountdownTimer);
}

// ── Attack Injection ──────────────────────────────────────────────────────────
async function injectAttack(type) {
  const feedback = $('inject-feedback');
  feedback.classList.remove('hidden');
  feedback.textContent = `⏳ Injecting ${type.replace(/_/g, ' ')} attack…`;
  feedback.style.borderColor = '';
  feedback.style.color = '';

  try {
    const res = await fetch(`/api/inject-attack/${type}`, { method: 'POST' });
    const data = await res.json();

    if (res.ok) {
      if (data.status === 'already_running') {
        feedback.textContent = `⚠ ${data.attack_type.replace(/_/g, ' ')} pipeline already running — wait for it to finish`;
        feedback.style.borderColor = 'rgba(251,191,36,0.4)';
        feedback.style.color = 'var(--yellow, #fbbf24)';
      } else {
        feedback.textContent = `✓ Attack injected → ${data.target_node} | Agent pipeline starting…`;
        feedback.style.borderColor = 'rgba(34,197,94,0.4)';
        feedback.style.color = 'var(--green)';
      }
      setTimeout(() => {
        feedback.classList.add('hidden');
        feedback.style.borderColor = '';
        feedback.style.color = '';
      }, 5000);
    } else {
      feedback.textContent = `✗ Injection failed: ${data.detail || 'unknown error'}`;
      feedback.style.color = 'var(--red)';
    }
  } catch (e) {
    feedback.textContent = `✗ Network error: ${e.message}`;
    feedback.style.color = 'var(--red)';
  }
}

// ── Incident Reports ──────────────────────────────────────────────────────────
async function pollReports() {
  try {
    const res = await fetch('/api/reports');
    if (!res.ok) return;
    const data = await res.json();
    renderReports(data.reports || []);
  } catch (e) { /* silent */ }
}

function renderReports(reports) {
  if (!reports || reports.length === state.reports.length) return;
  state.reports = reports;

  const list = $('reports-list');
  $('report-count').textContent = `${reports.length} report${reports.length !== 1 ? 's' : ''}`;
  list.innerHTML = '';

  if (reports.length === 0) {
    list.innerHTML = `
      <div class="timeline-empty">
        <div class="empty-icon">📭</div>
        <div>No incidents resolved yet</div>
      </div>`;
    return;
  }

  reports.forEach(r => {
    const card = document.createElement('div');
    card.className = `report-card sev-${r.classification || 'INFO'}`;
    card.innerHTML = `
      <div class="report-card-top">
        <span class="report-card-id">#${escHtml(r.report_id || r.incident_id)}</span>
        <span class="report-card-time">${formatTime(r.generated_at)}</span>
      </div>
      <div class="report-card-title">${escHtml(r.title || 'Incident Report')}</div>
      <div class="report-card-summary">${escHtml((r.executive_summary || '').substring(0, 120))}…</div>
    `;
    card.addEventListener('click', () => openReportModal(r));
    list.appendChild(card);
  });
}

function openReportModal(report) {
  state.currentReport = report;
  $('replay-btn').classList.toggle('hidden', !report.incident_id);
  $('report-modal-title').textContent = report.title || 'Incident Report';

  const body = $('report-modal-body');
  body.innerHTML = '';

  [
    { title: 'Executive Summary', text: report.executive_summary },
    { title: 'What Happened', text: report.what_happened },
    { title: 'What the Agent Did', text: report.what_agent_did },
    { title: 'Why Agent Responded', text: report.why_agent_responded },
    { title: 'Outcome', text: report.outcome },
  ].forEach(s => {
    if (!s.text) return;
    const sec = document.createElement('div');
    sec.className = 'report-section';
    sec.innerHTML = `
      <div class="report-section-title">${escHtml(s.title)}</div>
      <div class="report-section-body">${escHtml(s.text)}</div>`;
    body.appendChild(sec);
  });

  if (report.mitre_techniques && report.mitre_techniques.length > 0) {
    const sec = document.createElement('div');
    sec.className = 'report-section';
    sec.innerHTML = `<div class="report-section-title">MITRE ATT&CK ICS Techniques</div>
      <div class="report-tags">${report.mitre_techniques.map(t =>
      `<span class="report-tag tag-mitre" title="${escHtml(t.url || '')}">${escHtml(t.id)} — ${escHtml(t.name)}</span>`
    ).join('')}</div>`;
    body.appendChild(sec);
  }

  if (report.cves && report.cves.length > 0) {
    const sec = document.createElement('div');
    sec.className = 'report-section';
    sec.innerHTML = `<div class="report-section-title">CVEs Identified</div>
      <div class="report-tags">${report.cves.map(c =>
      `<span class="report-tag tag-cve">${escHtml(c.id)} CVSS:${c.cvss_score || '?'} (${escHtml(c.severity || '?')})</span>`
    ).join('')}</div>`;
    body.appendChild(sec);
  }

  if (report.actions_taken && report.actions_taken.length > 0) {
    const sec = document.createElement('div');
    sec.className = 'report-section';
    sec.innerHTML = `<div class="report-section-title">Actions Executed</div>
      <div class="report-tags">${report.actions_taken.map(a =>
      `<span class="report-tag tag-action">${escHtml(String(a).replace(/_/g, ' '))}</span>`
    ).join('')}</div>`;
    body.appendChild(sec);
  }

  const meta = document.createElement('div');
  meta.className = 'report-section';
  meta.innerHTML = `<div class="report-section-title">Metadata</div>
    <div class="report-section-body">
      <b>Incident ID:</b> ${escHtml(report.incident_id || '—')}<br/>
      <b>Classification:</b> ${escHtml(report.classification || '—')}<br/>
      <b>Playbook:</b> ${escHtml(report.playbook_executed || '—')}<br/>
      <b>Human Approval:</b> ${escHtml(report.human_approval || '—')}<br/>
      <b>Agent Confidence:</b> ${report.agent_confidence != null ? (report.agent_confidence * 100).toFixed(0) + '%' : '—'}<br/>
      <b>False Positive Probability:</b> ${report.false_positive_probability != null ? (report.false_positive_probability * 100).toFixed(0) + '%' : '—'}
    </div>`;
  body.appendChild(meta);

  $('report-overlay').classList.remove('hidden');
}

async function openIncidentReplay() {
  const report = state.currentReport;
  if (!report || !report.incident_id) return;
  const body = $('report-modal-body');
  body.innerHTML = '<div class="timeline-empty">Loading decision replay…</div>';
  try {
    const response = await fetch(`/api/incidents/${encodeURIComponent(report.incident_id)}/replay`);
    if (!response.ok) throw new Error(`Replay unavailable (${response.status})`);
    const replay = await response.json();
    $('report-modal-title').textContent = `Decision Replay — ${replay.incident_id}`;
    body.innerHTML = '';

    const evaluation = replay.evaluation || {};
    const summary = document.createElement('div');
    summary.className = 'report-section';
    summary.innerHTML = `<div class="report-section-title">Replay Summary</div>
      <div class="report-section-body">
        <b>Status:</b> ${escHtml(replay.status || 'unknown')}<br/>
        <b>Attack:</b> ${escHtml(replay.attack_type || 'unknown')}<br/>
        <b>Node:</b> ${escHtml(replay.node_id || 'unknown')}<br/>
        <b>Quality:</b> ${evaluation.quality_score ?? '—'}<br/>
        <b>Hallucination flagged:</b> ${evaluation.hallucination_flagged ? 'Yes' : 'No'}
      </div>`;
    body.appendChild(summary);

    (replay.events || []).forEach(event => {
      const item = document.createElement('div');
      item.className = 'replay-event';
      item.innerHTML = `
        <div class="replay-event-meta">${formatTime(event.timestamp)} · ${escHtml(event.agent)} · ${escHtml(event.action)}</div>
        <div>${escHtml(event.reasoning || '')}</div>`;
      body.appendChild(item);
    });
  } catch (error) {
    body.innerHTML = `<div class="timeline-empty">${escHtml(error.message)}</div>`;
  }
}

function closeReportModal() {
  $('report-overlay').classList.add('hidden');
  state.currentReport = null;
}

$('report-overlay').addEventListener('click', (e) => {
  if (e.target === $('report-overlay')) closeReportModal();
});

// ── Arize Phoenix Stats ───────────────────────────────────────────────────────
async function pollPhoenixStats() {
  try {
    const res = await fetch('/api/phoenix-stats');
    if (!res.ok) return;
    const data = await res.json();

    $('pstat-traces').textContent = data.total_traces ?? '—';
    $('pstat-hallucinations').textContent = data.hallucination_flags ?? '—';
    $('pstat-quality').textContent = data.avg_quality_score != null
      ? data.avg_quality_score.toFixed(2) : '—';

    const observable = data.status === 'connected' || data.status === 'local';
    const phoenixDisabled = data.status === 'disabled';
    $('pstat-status').textContent = data.status === 'connected' ? '✓ Cloud'
      : data.status === 'local' ? '✓ Local'
        : phoenixDisabled ? '○ Disabled' : '⚠ Offline';
    $('pstat-status').className = 'pstat-value ' + (observable ? 'pstat-good' : 'pstat-warn');

    $('pill-phoenix-val').textContent = observable
      ? `Observability: ${data.total_traces} traces`
      : (phoenixDisabled ? 'Phoenix: Disabled' : 'Phoenix: Offline');

    if (data.phoenix_url) $('phoenix-link').href = data.phoenix_url;
  } catch (e) {
    $('pill-phoenix-val').textContent = 'Phoenix: Offline';
  }
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function startClock() {
  function tick() {
    const now = new Date();
    $('system-time').textContent = now.toUTCString().split(' ')[4] + ' UTC';
  }
  tick();
  setInterval(tick, 1000);
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString('en-GB', { hour12: false });
  } catch { return '—'; }
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
