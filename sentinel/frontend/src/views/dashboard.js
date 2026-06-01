import { fetchApi } from '../api.js';
import { renderEvolution } from '../charts/evolution.js';
import { renderDonut } from '../charts/donut.js';

let _currentProject = null;
let _currentRange = '24h';
let _projects = [];

function kpiCard(label, value, mod = '') {
  return `<div class="kpi-card ${mod}">
    <div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>
  </div>`;
}

function urgenceItem(tracker) {
  const sinceMin = tracker._lastSeenSeconds > 0 ? Math.floor(tracker._lastSeenSeconds / 60) : '?';
  const sev = tracker._lastSeenSeconds > 7200 ? 'critical' : 'warning';
  const label = sev === 'critical' ? 'Critique' : 'Avertissement';
  return `<li class="urgence-item">
    <span class="badge badge-${sev}">${label}</span>
    <span>${tracker.name}</span>
    <span class="status-${sev === 'critical' ? 'archive' : 'se_terminant'}" style="color:var(--text-muted);font-size:12px">
      ${tracker._projectName || 'Sans projet'} - hors ligne depuis ${sinceMin} min
    </span>
  </li>`;
}

async function loadSnapshots(projectId, range) {
  const params = new URLSearchParams({ range });
  if (projectId) params.set('project', projectId);
  return fetchApi(`/sentinel/api/snapshots?${params}`);
}

export async function renderDashboard(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';

  const [kpis, trackers, projectsData] = await Promise.all([
    fetchApi('/sentinel/api/kpis'),
    fetchApi('/sentinel/api/trackers?limit=50'),
    fetchApi('/sentinel/api/projects'),
  ]);

  _projects = projectsData.projects || [];

  const urgents = (trackers.trackers || []).filter(t => !t._isConnected && t._lastSeenSeconds > 60);
  urgents.sort((a, b) => b._lastSeenSeconds - a._lastSeenSeconds);

  const snapshotData = await loadSnapshots(_currentProject, _currentRange);

  const projectOptions = _projects.map(p =>
    `<option value="${p._id}" ${_currentProject === p._id ? 'selected' : ''}>${p.name}</option>`
  ).join('');

  container.innerHTML = `
    <div class="kpi-grid">
      ${kpiCard('Projets actifs', kpis.activeProjects, 'accent')}
      ${kpiCard('Connectés', kpis.connected, 'accent')}
      ${kpiCard('Déconnectés', kpis.disconnected, kpis.disconnected > 0 ? 'danger' : '')}
      ${kpiCard('Batterie faible', kpis.batteryLow, kpis.batteryLow > 0 ? 'warning' : '')}
      ${kpiCard('Urgences', kpis.urgences, kpis.urgences > 0 ? 'danger' : '')}
    </div>

    ${urgents.length > 0 ? `
    <div class="panel">
      <div class="panel-title">Urgences — ${urgents.length} tracker(s) hors ligne</div>
      <ul class="urgence-list">
        ${urgents.slice(0, 20).map(urgenceItem).join('')}
      </ul>
    </div>` : ''}

    <div class="chart-row">
      <div class="panel">
        <div class="panel-title">Évolution</div>
        <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
          <select id="project-selector" style="background:var(--panel);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:5px 10px;font-size:12px;font-family:inherit">
            <option value="">Tous les projets</option>
            ${projectOptions}
          </select>
          <div class="range-selector">
            ${['6h','24h','7d'].map(r =>
              `<button class="range-btn ${_currentRange === r ? 'active' : ''}" data-range="${r}">${r}</button>`
            ).join('')}
          </div>
        </div>
        <div id="chart-evolution" class="chart-container"></div>
      </div>
      <div class="panel">
        <div class="panel-title">Répartition</div>
        <div id="chart-donut" class="chart-container" style="min-height:220px"></div>
      </div>
    </div>
    <div style="color:var(--text-muted);font-size:11px;text-align:right">
      Dernière mise à jour : ${new Date(kpis.loadedAt).toLocaleTimeString('fr-FR')}
    </div>
  `;

  renderEvolution(document.getElementById('chart-evolution'), snapshotData.snapshots);
  renderDonut(document.getElementById('chart-donut'), kpis);

  document.getElementById('project-selector').addEventListener('change', async (e) => {
    _currentProject = e.target.value || null;
    const snap = await loadSnapshots(_currentProject, _currentRange);
    renderEvolution(document.getElementById('chart-evolution'), snap.snapshots);
  });

  container.querySelectorAll('.range-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      _currentRange = btn.dataset.range;
      container.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const snap = await loadSnapshots(_currentProject, _currentRange);
      renderEvolution(document.getElementById('chart-evolution'), snap.snapshots);
    });
  });
}
