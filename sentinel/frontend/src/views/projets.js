import { fetchApi } from '../api.js';

let _filter = 'actif';
let _search = '';
let _projects = [];

function statusLabel(status) {
  const map = {
    actif:        'Actif',
    se_terminant: 'Se terminant',
    archive:      'Archivé',
    termine:      'Terminé',
  };
  return map[status] || status;
}

function scoreBar(score) {
  const color = score > 70 ? 'var(--accent)' : score > 40 ? 'var(--warning)' : 'var(--danger)';
  return `<div style="display:flex;align-items:center;gap:6px">
    <div style="flex:1;height:4px;background:var(--border);border-radius:2px;max-width:60px">
      <div style="width:${score}%;height:4px;background:${color};border-radius:2px"></div>
    </div>
    <span style="font-size:13px;color:var(--text-muted)">${score}</span>
  </div>`;
}

function projectCard(p) {
  const startFmt = p.startDate ? new Date(p.startDate).toLocaleDateString('fr-FR') : '-';
  const endFmt   = p.endDate   ? new Date(p.endDate).toLocaleDateString('fr-FR')   : '-';
  return `
    <div class="project-card" data-id="${p._id}">
      <div class="card-title">${p.name}</div>
      <div class="card-code">${p.code || ''}</div>
      <div style="font-size:13px;color:var(--text-muted);margin-bottom:12px">${startFmt} – ${endFmt}</div>
      <div class="card-meta">
        <span>${p._trackerCount} dispositif${p._trackerCount > 1 ? 's' : ''}</span>
        ${scoreBar(p._healthScore)}
        <span class="status-${p._status}">${statusLabel(p._status)}</span>
      </div>
    </div>`;
}

async function renderDetail(container, projectId) {
  container.innerHTML = '<div class="loading">Chargement du projet...</div>';
  const p = await fetchApi(`/sentinel/api/projects/${projectId}`);

  const trackerRows = (p.trackers || []).map(t => `
    <tr>
      <td>${t.name}</td>
      <td>${t._isConnected
        ? '<span class="dot dot-green"></span>Connecté'
        : '<span class="dot dot-red"></span>Déconnecté'}</td>
      <td>${t._batteryStatus === 'ok'
        ? '<span style="color:var(--accent)">OK</span>'
        : t._batteryStatus === 'faible'
          ? '<span style="color:var(--warning)">Faible</span>'
          : 'Inconnu'}
        ${t._batteryVolt > 0 ? `(${t._batteryVolt.toFixed(2)} V)` : ''}</td>
      <td style="color:var(--text-muted)">${t._healthScore}</td>
    </tr>`).join('');

  container.innerHTML = `
    <div style="margin-bottom:16px">
      <button id="btn-back" class="btn-primary"
        style="background:transparent;border:1px solid var(--border);color:var(--text)">
        &laquo; Retour aux projets
      </button>
    </div>
    <div class="panel">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:20px">
        <div>
          <h2 style="font-size:19px;font-weight:700;margin-bottom:4px">${p.name}</h2>
          <div style="color:var(--text-muted);font-size:14px">${p.code || ''}</div>
        </div>
        <span class="status-${p._status}" style="font-size:14px;font-weight:600">${statusLabel(p._status)}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:20px">
        <div><div class="proj-stat-label">Début</div>${p.startDate ? new Date(p.startDate).toLocaleDateString('fr-FR') : '-'}</div>
        <div><div class="proj-stat-label">Fin</div>${p.endDate ? new Date(p.endDate).toLocaleDateString('fr-FR') : '-'}</div>
        <div><div class="proj-stat-label">Dispositifs</div>${p._trackerCount}</div>
        <div><div class="proj-stat-label">Score santé</div>${scoreBar(p._healthScore)}</div>
      </div>
      ${(p.trackers || []).length === 0
        ? '<div class="empty-state">Aucun dispositif dans ce projet.</div>'
        : `<table class="data-table">
             <thead><tr><th>Dispositif</th><th>Connexion</th><th>Batterie</th><th>Score santé</th></tr></thead>
             <tbody>${trackerRows}</tbody>
           </table>`}
    </div>`;

  container.querySelector('#btn-back').addEventListener('click', () => renderProjets(container));
}

function applyFilters() {
  return _projects.filter(p => {
    if (_filter !== 'all' && p._status !== _filter) return false;
    if (_search) {
      const q = _search.toLowerCase();
      if (!p.name.toLowerCase().includes(q) && !(p.code || '').toLowerCase().includes(q)) return false;
    }
    return true;
  });
}

function countByStatus(projects) {
  const c = { all: projects.length, actif: 0, se_terminant: 0, archive: 0, termine: 0 };
  for (const p of projects) if (p._status in c) c[p._status]++;
  return c;
}

// ── Navigation externe (KPI cliquable → filtre pré-appliqué) ──────────────────

export function applyFilter(status) {
  if (status !== undefined) _filter = status;
  const pane = document.getElementById('view-projets');
  if (pane && pane.children.length) renderList(pane, applyFilters());
}

export async function renderProjets(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';
  const data = await fetchApi('/sentinel/api/projects');
  _projects = data.projects || [];
  renderList(container, applyFilters());
}

function renderList(container, filtered) {
  const counts  = countByStatus(_projects);
  const filters = ['all', 'actif', 'se_terminant', 'archive', 'termine'];

  const chips = filters.map(f => {
    const label = f === 'all' ? 'Tous' : statusLabel(f);
    const count = counts[f] ?? 0;
    return `<button class="seg-chip ${_filter === f ? 'active' : ''}" data-status="${f}">
      ${label}<span class="seg-count">${count}</span>
    </button>`;
  }).join('');

  container.innerHTML = `
    <div class="proj-toolbar">
      <div class="seg-group">${chips}</div>
      <input class="disp-search" type="text" id="search-projects"
        placeholder="Rechercher par nom ou code…" value="${_search}" />
    </div>
    ${filtered.length === 0
      ? '<div class="empty-state">Aucun projet correspondant à ce filtre.</div>'
      : `<div class="cards-grid">${filtered.map(projectCard).join('')}</div>`}
  `;

  container.querySelectorAll('.seg-chip[data-status]').forEach(btn => {
    btn.addEventListener('click', () => {
      _filter = btn.dataset.status;
      renderList(container, applyFilters());
    });
  });

  container.querySelector('#search-projects').addEventListener('input', e => {
    _search = e.target.value;
    renderList(container, applyFilters());
  });

  container.querySelectorAll('.project-card[data-id]').forEach(card => {
    card.addEventListener('click', () => renderDetail(container, card.dataset.id));
  });
}
