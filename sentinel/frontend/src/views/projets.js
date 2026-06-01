import { fetchApi } from '../api.js';

let _filter = 'all';
let _search = '';
let _projects = [];

function statusLabel(status) {
  const map = {
    actif: 'Actif',
    se_terminant: 'Se terminant',
    archive: 'Archivé',
    termine: 'Terminé',
  };
  return map[status] || status;
}

function scoreBar(score) {
  const color = score > 70 ? 'var(--accent)' : score > 40 ? 'var(--warning)' : 'var(--danger)';
  return `<div style="display:flex;align-items:center;gap:6px">
    <div style="flex:1;height:4px;background:var(--border);border-radius:2px;max-width:60px">
      <div style="width:${score}%;height:4px;background:${color};border-radius:2px"></div>
    </div>
    <span style="font-size:12px;color:var(--text-muted)">${score}</span>
  </div>`;
}

function projectCard(p) {
  const startFmt = p.startDate ? new Date(p.startDate).toLocaleDateString('fr-FR') : '-';
  const endFmt = p.endDate ? new Date(p.endDate).toLocaleDateString('fr-FR') : '-';
  return `
    <div class="project-card" data-id="${p._id}">
      <div class="card-title">${p.name}</div>
      <div class="card-code">${p.code || ''}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:12px">${startFmt} - ${endFmt}</div>
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
      <td>${t._isConnected ? '<span class="dot dot-green"></span>Connecte' : '<span class="dot dot-red"></span>Deconnecte'}</td>
      <td>${t._batteryStatus === 'ok' ? '<span style="color:var(--accent)">OK</span>' : t._batteryStatus === 'faible' ? '<span style="color:var(--warning)">Faible</span>' : 'Inconnu'}
        ${t._batteryVolt > 0 ? `(${t._batteryVolt.toFixed(2)}V)` : ''}</td>
      <td style="color:var(--text-muted)">${t._healthScore}</td>
    </tr>`).join('');

  container.innerHTML = `
    <div style="margin-bottom:16px">
      <button id="btn-back" class="btn-primary" style="background:transparent;border:1px solid var(--border);color:var(--text)">&laquo; Retour aux projets</button>
    </div>
    <div class="panel">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:20px">
        <div>
          <h2 style="font-size:18px;font-weight:700;margin-bottom:4px">${p.name}</h2>
          <div style="color:var(--text-muted);font-size:13px">${p.code || ''}</div>
        </div>
        <span class="status-${p._status}" style="font-size:13px;font-weight:600">${statusLabel(p._status)}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:20px">
        <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Debut</div>${p.startDate ? new Date(p.startDate).toLocaleDateString('fr-FR') : '-'}</div>
        <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Fin</div>${p.endDate ? new Date(p.endDate).toLocaleDateString('fr-FR') : '-'}</div>
        <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Dispositifs</div>${p._trackerCount}</div>
        <div><div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Score sante</div>${scoreBar(p._healthScore)}</div>
      </div>
      ${(p.trackers || []).length === 0 ? '<div class="empty-state">Aucun dispositif dans ce projet.</div>' : `
      <table class="data-table">
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

export async function renderProjets(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';
  const data = await fetchApi('/sentinel/api/projects');
  _projects = data.projects || [];

  const filtered = applyFilters();
  renderList(container, filtered);
}

function renderList(container, filtered) {
  const filters = ['all', 'actif', 'se_terminant', 'archive', 'termine'];
  const filterBtns = filters.map(f => `
    <button class="tab-btn filter-status ${_filter === f ? 'active' : ''}" data-status="${f}">
      ${f === 'all' ? 'Tous' : statusLabel(f)}
    </button>`
  ).join('');

  container.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:20px">
      <div class="range-selector">${filterBtns}</div>
      <input type="text" placeholder="Rechercher par nom ou code..." value="${_search}"
        id="search-projects" style="flex:1;min-width:200px;background:var(--panel);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:7px 12px;font-size:13px;font-family:inherit" />
    </div>
    ${filtered.length === 0
      ? '<div class="empty-state">Aucun projet correspondant à ce filtre.</div>'
      : `<div class="cards-grid">${filtered.map(projectCard).join('')}</div>`}
  `;

  container.querySelectorAll('.filter-status').forEach(btn => {
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
