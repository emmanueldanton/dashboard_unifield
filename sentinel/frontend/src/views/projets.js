import { fetchApi } from '../api.js';

let _filter = 'actif';
let _search = '';
let _typeFilter = 'Tous';
let _projects = [];

function statusLabel(status) {
  const map = {
    actif:        'Actif',
    se_terminant: 'Fin imminente',
    inactif:      'Inactif',
    archive:      'Archivé',
    termine:      'Récemment terminé',
  };
  return map[status] || status;
}

function fmtLastActivity(iso, tz) {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      timeZone: tz || 'UTC',
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return new Date(iso).toLocaleString('fr-FR');
  }
}

function scoreBar(score) {
  const color = score > 70 ? 'var(--accent)' : score > 40 ? 'var(--warning)' : 'var(--danger)';
  return `<div style="display:flex;align-items:center;gap:6px">
    <div style="flex:1;height:4px;background:var(--border);border-radius:2px;max-width:60px">
      <div style="width:${score}%;height:4px;background:${color};border-radius:2px"></div>
    </div>
    <span style="font-size:13px;color:var(--text-muted)">${score}%</span>
  </div>`;
}

function projectCard(p) {
  const endFmt  = p.endDate ? new Date(p.endDate).toLocaleDateString('fr-FR') : null;
  const conn    = p._connectedCount ?? 0;
  const total   = p._trackerCount ?? 0;
  const bat     = p._batteryLowCount ?? 0;
  const type    = p.type || '';

  const battLine = bat > 0
    ? ` <span class="card-batt">· ${bat} batt. faible</span>`
    : '';

  const tz     = p._timezone && p._timezone !== 'UTC' ? p._timezone : null;
  const endLine = endFmt ? `<span class="card-end">→ ${endFmt}</span>` : '';

  // Mentions de cycle de vie : affichées en plus du statut quand le projet est actif
  // (évite la redondance si le statut primaire est déjà "terminé"/"fin imminente")
  const mentions = [];
  if (p._status === 'actif') {
    if (p._ended)      mentions.push(`<span class="card-mention card-mention--ended">Terminé</span>`);
    if (p._endingSoon) mentions.push(`<span class="card-mention card-mention--ending">Fin imminente</span>`);
  }
  const mentionsHtml = mentions.join('');

  return `
    <div class="project-card" data-id="${p._id}">
      <div class="card-pill-row">
        <span class="card-name-pill">${p.name}</span>
        ${type ? `<span class="card-type-tag">${type}</span>` : ''}
      </div>
      <div class="card-hero">
        <span class="card-hero-num">${conn}</span>
        <span class="card-hero-lbl">connectés / ${total}</span>
      </div>
      <div class="card-conn-row">
        ${total > 0 ? `${total - conn} hors ligne${battLine}` : '—'}
      </div>
      <div class="card-divider"></div>
      <div class="card-status-footer">
        <span class="card-status-dot card-status-dot--${p._status}"></span>
        <span class="status-${p._status}">${statusLabel(p._status)}</span>
        ${mentionsHtml}
        ${tz ? `<span class="card-tz-tag">${tz}</span>` : ''}
        ${endLine}
      </div>
    </div>`;
}

async function renderDetail(container, projectId) {
  container.innerHTML = '<div class="loading">Chargement du projet...</div>';
  const p = await fetchApi(`/sentinel/api/projects/${projectId}`);

  const trackerRows = (p.trackers || []).map(t => {
    const lastSeen = t._lastSeenSeconds >= 0
      ? (t._lastSeenSeconds < 60
        ? `${t._lastSeenSeconds}s`
        : t._lastSeenSeconds < 3600
          ? `${Math.floor(t._lastSeenSeconds / 60)}min`
          : `${Math.floor(t._lastSeenSeconds / 3600)}h`)
      : '-';
    return `
      <tr>
        <td>${t.name}</td>
        <td>${t._unitName && t._unitName !== '-' ? t._unitName : '<span style="color:var(--text-muted)">-</span>'}</td>
        <td>${t._isConnected
          ? '<span class="dot dot-green"></span>Connecté'
          : '<span class="dot dot-red"></span>Déconnecté'}</td>
        <td>${t._batteryStatus === 'ok'
          ? '<span style="color:var(--accent)">OK</span>'
          : t._batteryStatus === 'faible'
            ? '<span style="color:var(--warning)">Faible</span>'
            : 'Inconnu'}
          ${t._batteryVolt > 0 ? `(${t._batteryVolt.toFixed(2)} V)` : ''}</td>
        <td style="color:var(--text-muted)">${lastSeen}</td>
        <td style="color:var(--text-muted)">${t._healthScore}</td>
      </tr>`;
  }).join('');

  const lastAct = fmtLastActivity(p._lastActivity, p._timezone);
  const tz = p._timezone && p._timezone !== 'UTC' ? p._timezone : 'UTC';

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
          ${p.type ? `<div style="margin-top:4px"><span class="proj-type-chip">${p.type}</span></div>` : ''}
        </div>
        <span class="status-${p._status}" style="font-size:14px;font-weight:600">${statusLabel(p._status)}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:20px">
        <div><div class="proj-stat-label">Début</div>${p.startDate ? new Date(p.startDate).toLocaleDateString('fr-FR') : '-'}</div>
        <div><div class="proj-stat-label">Fin</div>${p.endDate ? new Date(p.endDate).toLocaleDateString('fr-FR') : '-'}</div>
        <div><div class="proj-stat-label">Capteurs</div>${p._trackerCount}</div>
        <div><div class="proj-stat-label">Connectés</div><span style="color:var(--accent)">${p._connectedCount ?? '-'}</span></div>
        <div><div class="proj-stat-label">Batt. faible</div><span style="color:var(--warning)">${p._batteryLowCount ?? '-'}</span></div>
        <div><div class="proj-stat-label">Dernière activité</div>${lastAct}</div>
        <div><div class="proj-stat-label">Fuseau</div>${tz}</div>
        <div><div class="proj-stat-label">Score santé</div>${scoreBar(p._healthScore)}</div>
      </div>
      ${(p.trackers || []).length === 0
        ? '<div class="empty-state">Aucun dispositif dans ce projet.</div>'
        : `<table class="data-table">
             <thead><tr><th>Dispositif</th><th>Unité</th><th>Connexion</th><th>Batterie</th><th>Vu il y a</th><th>Score santé</th></tr></thead>
             <tbody>${trackerRows}</tbody>
           </table>`}
    </div>`;

  container.querySelector('#btn-back').addEventListener('click', () => renderProjets(container));
}

// Un projet correspond-il à un filtre de statut ?
// Les filtres cycle de vie tiennent compte des flags pour rester cohérents avec les KPIs :
// un projet actif ET en fin imminente apparaît dans "Actif" ET dans "Fin imminente".
function matchesStatusFilter(p, filter) {
  if (filter === 'all')          return true;
  if (filter === 'se_terminant') return p._status === 'se_terminant' || (p._status === 'actif' && p._endingSoon);
  if (filter === 'termine')      return p._status === 'termine' || (p._status === 'actif' && p._ended);
  return p._status === filter;
}

function applyFilters() {
  const filtered = _projects.filter(p => {
    if (!matchesStatusFilter(p, _filter)) return false;
    if (_typeFilter !== 'Tous' && (p.type || '') !== _typeFilter) return false;
    if (_search) {
      const q = _search.toLowerCase();
      if (!p.name.toLowerCase().includes(q) && !(p.code || '').toLowerCase().includes(q)) return false;
    }
    return true;
  });
  // Tri par activité la plus récente en premier (null = jamais actif → en dernier)
  return filtered.sort((a, b) => {
    if (!a._lastActivity && !b._lastActivity) return 0;
    if (!a._lastActivity) return 1;
    if (!b._lastActivity) return -1;
    return b._lastActivity > a._lastActivity ? 1 : -1;
  });
}

function countByStatus(projects) {
  const c = { all: projects.length, actif: 0, se_terminant: 0, inactif: 0, archive: 0, termine: 0 };
  for (const f of ['actif', 'se_terminant', 'inactif', 'archive', 'termine']) {
    c[f] = projects.filter(p => matchesStatusFilter(p, f)).length;
  }
  return c;
}

function getTypes(projects) {
  const types = new Set();
  for (const p of projects) if (p.type && p.type !== 'KYD') types.add(p.type);
  return ['Tous', ...Array.from(types).sort()];
}

// ── Navigation externe (KPI cliquable → filtre pré-appliqué) ──────────────────

export function applyFilter({ status, search } = {}) {
  if (status !== undefined) _filter = status;
  if (search !== undefined) _search = search;
  const pane = document.getElementById('view-projets');
  if (pane && pane.querySelector('#proj-chips')) updateList(pane);
}

export async function renderProjets(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';
  const data = await fetchApi('/sentinel/api/projects');
  _projects = data.projects || [];

  const types = getTypes(_projects);
  const typeSelect = types.length > 1
    ? `<select class="filter-select" id="filter-type">
        ${types.map(t => `<option value="${t}" ${_typeFilter === t ? 'selected' : ''}>${t}</option>`).join('')}
       </select>`
    : '';

  container.innerHTML = `
    <div class="proj-toolbar">
      <input class="disp-search" type="text" id="search-projects"
        placeholder="Rechercher par nom ou code…" value="${_search}" />
      ${typeSelect ? typeSelect + '<div class="seg-divider"></div>' : ''}
      <div id="proj-chips" class="seg-group"></div>
    </div>
    <div id="proj-cards"></div>
  `;

  container.querySelector('#search-projects').addEventListener('input', e => {
    _search = e.target.value;
    updateList(container);
  });

  const typeEl = container.querySelector('#filter-type');
  if (typeEl) {
    typeEl.addEventListener('change', e => {
      _typeFilter = e.target.value;
      updateList(container);
    });
  }

  container.querySelector('#proj-chips').addEventListener('click', e => {
    const btn = e.target.closest('.seg-chip[data-status]');
    if (!btn) return;
    _filter = btn.dataset.status;
    updateList(container);
  });

  updateList(container);
}

function updateList(container) {
  const filtered = applyFilters();
  const counts   = countByStatus(_projects);
  const statusFilters = ['all', 'actif', 'se_terminant', 'inactif', 'archive', 'termine'];

  container.querySelector('#proj-chips').innerHTML = statusFilters.map(f => {
    const label = f === 'all' ? 'Tous' : statusLabel(f);
    return `<button class="seg-chip ${_filter === f ? 'active' : ''}" data-status="${f}">
      ${label}<span class="seg-count">${counts[f] ?? 0}</span>
    </button>`;
  }).join('');

  const cardsEl = container.querySelector('#proj-cards');
  cardsEl.innerHTML = filtered.length === 0
    ? '<div class="empty-state">Aucun projet correspondant à ce filtre.</div>'
    : `<div class="cards-grid">${filtered.map(projectCard).join('')}</div>`;

  cardsEl.querySelectorAll('.project-card[data-id]').forEach(card => {
    card.addEventListener('click', () => renderDetail(container, card.dataset.id));
  });
}
