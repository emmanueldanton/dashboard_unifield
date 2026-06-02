import { fetchApi } from '../api.js';

const PAGE_SIZE = 50;

const state = {
  all: [],
  search: '',
  status: 'connected',   // all | connected | disconnected (defaut Python : Connectés)
  battery: 'all',        // all | ok | faible | inconnu
  projects: new Set(),   // vide = tous
  sort: '_lastSeenSeconds',
  dir: 'asc',
  page: 1,
  selected: null,
};

// ── Helpers d'affichage ───────────────────────────────────────────────────────

function formatSince(secs) {
  if (secs == null || secs < 0) return 'Jamais';
  if (secs < 60) return `il y a ${secs}s`;
  if (secs < 3600) return `il y a ${Math.floor(secs / 60)}min`;
  if (secs < 86400) return `il y a ${Math.floor(secs / 3600)}h`;
  return `il y a ${Math.floor(secs / 86400)}j`;
}

function formatLocal(iso, tz) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      timeZone: tz || 'UTC', day: '2-digit', month: '2-digit',
      hour: '2-digit', minute: '2-digit',
    }).format(d);
  } catch {
    return d.toLocaleString('fr-FR');
  }
}

function battBadge(status, volt) {
  const v = (typeof volt === 'number' && volt > 0) ? `${volt.toFixed(2)}V` : '';
  if (status === 'ok') return `<span class="batt-pill batt-ok">${v || 'OK'}</span>`;
  if (status === 'faible') return `<span class="batt-pill batt-low">${v || 'Faible'} ⚠</span>`;
  return `<span class="batt-pill batt-unknown">Inconnu</span>`;
}

function scoreBar(score) {
  const s = score ?? 0;
  const color = s > 70 ? 'var(--accent)' : s > 40 ? 'var(--warning)' : 'var(--danger)';
  return `<div class="score-cell">
    <div class="score-track"><div class="score-fill" style="width:${s}%;background:${color}"></div></div>
    <span class="score-num">${s}</span>
  </div>`;
}

function num(v, suffix = '', digits = 1) {
  return (typeof v === 'number' && v > 0) ? `${v.toFixed(digits)}${suffix}` : '-';
}

// ── Filtrage / tri (cote client) ───────────────────────────────────────────────

function matchSearch(t, q) {
  if (!q) return true;
  return [t.name, t._projectName, t._unitName].some(
    x => (x || '').toLowerCase().includes(q)
  );
}

function applyExcept(skip) {
  const q = state.search.trim().toLowerCase();
  return state.all.filter(t => {
    if (!matchSearch(t, q)) return false;
    if (skip !== 'project' && state.projects.size && !state.projects.has(t._projectId)) return false;
    if (skip !== 'status' && state.status === 'connected' && !t._isConnected) return false;
    if (skip !== 'status' && state.status === 'disconnected' && t._isConnected) return false;
    if (skip !== 'battery' && state.battery !== 'all' && t._batteryStatus !== state.battery) return false;
    return true;
  });
}

function currentList() {
  const list = applyExcept(null);
  const dir = state.dir === 'asc' ? 1 : -1;
  const f = state.sort;
  return list.sort((a, b) => {
    let av = a[f], bv = b[f];
    if (typeof av === 'string' || typeof bv === 'string') {
      return (av || '').localeCompare(bv || '') * dir;
    }
    av = av ?? -Infinity; bv = bv ?? -Infinity;
    return (av - bv) * dir;
  });
}

// ── Rendu ───────────────────────────────────────────────────────────────────

function chip(group, value, label, count, active) {
  return `<button class="seg-chip ${active ? 'active' : ''}" data-group="${group}" data-value="${value}">
    ${label}<span class="seg-count">${count}</span>
  </button>`;
}

function rowHtml(t) {
  const dot = t._isConnected ? 'dot-green' : 'dot-red';
  const statusTxt = t._isConnected ? 'Connecté' : 'Déconnecté';
  return `<tr data-id="${t._id}" class="${state.selected === t._id ? 'row-selected' : ''}">
    <td><span class="dot ${dot}"></span>${statusTxt}</td>
    <td class="cell-strong">${t.name || '?'}</td>
    <td>${t._projectName || '-'}<span class="cell-sub"> · ${t._unitName || '-'}</span></td>
    <td>${formatSince(t._lastSeenSeconds)}<span class="cell-sub"> · ${formatLocal(t.lastUpdate, t._projectTz)}</span></td>
    <td>${battBadge(t._batteryStatus, t._batteryVolt)}</td>
    <td>${num(t.temperature, '°C')}</td>
    <td>${(typeof t.weight === 'number' && t.weight >= 0) ? `${Math.round(t.weight)} kg` : '-'}</td>
    <td>${scoreBar(t._healthScore)}</td>
  </tr>`;
}

const COLS = [
  ['_isConnected', 'Statut'],
  ['name', 'Capteur'],
  ['_projectName', 'Projet · Unité'],
  ['_lastSeenSeconds', 'Dernière activité'],
  ['_batteryVolt', 'Batterie'],
  ['temperature', 'Temp.'],
  ['weight', 'Poids'],
  ['_healthScore', 'Score santé'],
];

function update(container) {
  const list = currentList();
  const totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  if (state.page > totalPages) state.page = totalPages;
  const start = (state.page - 1) * PAGE_SIZE;
  const pageItems = list.slice(start, start + PAGE_SIZE);

  // Compteurs des segments (chacun calcule en ignorant son propre groupe)
  const forStatus = applyExcept('status');
  const forBatt = applyExcept('battery');
  const counts = {
    status: {
      all: forStatus.length,
      connected: forStatus.filter(t => t._isConnected).length,
      disconnected: forStatus.filter(t => !t._isConnected).length,
    },
    battery: {
      all: forBatt.length,
      ok: forBatt.filter(t => t._batteryStatus === 'ok').length,
      faible: forBatt.filter(t => t._batteryStatus === 'faible').length,
      inconnu: forBatt.filter(t => t._batteryStatus === 'inconnu').length,
    },
  };

  container.querySelector('#seg-status').innerHTML =
    chip('status', 'all', 'Tous', counts.status.all, state.status === 'all') +
    chip('status', 'connected', 'Connectés', counts.status.connected, state.status === 'connected') +
    chip('status', 'disconnected', 'Déconnectés', counts.status.disconnected, state.status === 'disconnected');

  container.querySelector('#seg-battery').innerHTML =
    `<span class="seg-label">Batterie</span>` +
    chip('battery', 'all', 'Tous', counts.battery.all, state.battery === 'all') +
    chip('battery', 'ok', 'OK', counts.battery.ok, state.battery === 'ok') +
    chip('battery', 'faible', 'Faible', counts.battery.faible, state.battery === 'faible') +
    chip('battery', 'inconnu', '?', counts.battery.inconnu, state.battery === 'inconnu');

  const connTotal = state.all.filter(t => t._isConnected).length;
  container.querySelector('#disp-count').textContent =
    `${list.length} résultat(s) · ${connTotal} connectés / ${state.all.length} au total`;

  // En-tetes (indicateur de tri)
  container.querySelectorAll('th[data-sort]').forEach(th => {
    const f = th.dataset.sort;
    th.querySelector('.sort-ind').textContent =
      state.sort === f ? (state.dir === 'asc' ? ' ↑' : ' ↓') : '';
  });

  const tbody = container.querySelector('#disp-tbody');
  tbody.innerHTML = pageItems.length
    ? pageItems.map(rowHtml).join('')
    : '<tr><td colspan="8" class="empty-state">Aucun capteur ne correspond aux filtres.</td></tr>';

  tbody.querySelectorAll('tr[data-id]').forEach(tr => {
    tr.addEventListener('click', () => openDrawer(container, tr.dataset.id));
  });

  container.querySelector('#disp-pageinfo').textContent =
    `${list.length ? start + 1 : 0}–${Math.min(start + PAGE_SIZE, list.length)} sur ${list.length}`;
  container.querySelector('#disp-prev').disabled = state.page <= 1;
  container.querySelector('#disp-next').disabled = state.page >= totalPages;
}

// ── Drawer detail ─────────────────────────────────────────────────────────────

function statRow(label, value) {
  return `<div class="dw-stat"><div class="dw-stat-label">${label}</div><div class="dw-stat-value">${value}</div></div>`;
}

async function openDrawer(container, id) {
  state.selected = id;
  container.querySelectorAll('#disp-tbody tr').forEach(tr =>
    tr.classList.toggle('row-selected', tr.dataset.id === id));

  const t = state.all.find(x => x._id === id);
  const drawer = container.querySelector('#disp-drawer');
  const backdrop = container.querySelector('#disp-backdrop');
  if (!t) return;

  const gps = (t.lat && t.lon)
    ? `<a href="https://www.google.com/maps?q=${t.lat},${t.lon}" target="_blank" rel="noopener" class="gps-link">${t.lat.toFixed(5)}, ${t.lon.toFixed(5)} 📍</a>`
    : '-';

  drawer.innerHTML = `
    <div class="dw-header">
      <div>
        <div class="dw-title">${t.name || '?'}</div>
        <div class="dw-sub">${t._projectName || '-'} · ${t._unitName || '-'}</div>
      </div>
      <button class="dw-close" id="dw-close">✕</button>
    </div>
    <div class="dw-status ${t._isConnected ? 'is-conn' : 'is-disc'}">
      <span class="dot ${t._isConnected ? 'dot-green' : 'dot-red'}"></span>
      ${t._isConnected ? 'Connecté' : 'Déconnecté'} · ${formatSince(t._lastSeenSeconds)}
    </div>
    <div class="dw-grid">
      ${statRow('UUID', `<span class="dw-uuid">${t._id}</span><button class="dw-copy" data-copy="${t._id}" title="Copier l'UUID">⎘</button>`)}
      ${statRow('Dernière activité (locale)', formatLocal(t.lastUpdate, t._projectTz))}
      ${statRow('Allumage ce matin', '<span id="dw-boot">…</span>')}
      ${statRow('Batterie', num(t._batteryVolt, ' V', 2))}
      ${statRow('Peson batterie', num(t.shackleBattery, ' V', 2))}
      ${statRow('Température', num(t.temperature, ' °C'))}
      ${statRow('Poids', (typeof t.weight === 'number' && t.weight >= 0) ? `${Math.round(t.weight)} kg` : '-')}
      ${statRow('Score santé', `${t._healthScore ?? 0}%`)}
      ${statRow('GPS', gps)}
    </div>
    <div class="dw-section" id="dw-events-title">Historique events…</div>
    <div id="dw-events" class="dw-events"><div class="loading">Chargement…</div></div>
  `;

  drawer.classList.add('open');
  backdrop.classList.add('open');
  drawer.querySelector('#dw-close').addEventListener('click', () => closeDrawer(container));
  drawer.querySelector('.dw-copy')?.addEventListener('click', async e => {
    const val = e.currentTarget.dataset.copy;
    await navigator.clipboard.writeText(val);
    const btn = e.currentTarget;
    btn.textContent = '✓';
    setTimeout(() => { btn.textContent = '⎘'; }, 1500);
  });

  // Events (lazy)
  try {
    const detail = await fetchApi(`/sentinel/api/trackers/${encodeURIComponent(id)}`);
    if (state.selected !== id) return; // un autre capteur a ete ouvert entre-temps
    const bootEl = drawer.querySelector('#dw-boot');
    if (bootEl) bootEl.textContent = detail.bootThisMorning
      ? formatLocal(detail.bootThisMorning, t._projectTz) : 'Non détecté';

    drawer.querySelector('#dw-events-title').textContent =
      `Historique events — ${detail.eventsTotal} trouvé(s)`;
    const ev = detail.events || [];
    drawer.querySelector('#dw-events').innerHTML = ev.length
      ? ev.map(e => `<div class="dw-event">
          <div class="dw-event-ts">${formatLocal(e.ts, t._projectTz)}</div>
          <div class="dw-event-type">${e.type}</div>
          <div class="dw-event-msg">${e.message || ''}</div>
        </div>`).join('')
      : '<div class="empty-state" style="padding:16px">Aucun event pour ce capteur.</div>';
  } catch {
    const bootEl = drawer.querySelector('#dw-boot');
    if (bootEl) bootEl.textContent = '-';
    drawer.querySelector('#dw-events').innerHTML =
      '<div class="empty-state" style="padding:16px">Events indisponibles.</div>';
  }
}

function closeDrawer(container) {
  state.selected = null;
  container.querySelector('#disp-drawer').classList.remove('open');
  container.querySelector('#disp-backdrop').classList.remove('open');
  container.querySelectorAll('#disp-tbody tr').forEach(tr => tr.classList.remove('row-selected'));
}

// ── Navigation externe (KPI cliquable → filtre pré-appliqué) ──────────────────

export function applyFilter({ status, battery } = {}) {
  if (status  !== undefined) state.status  = status;
  if (battery !== undefined) state.battery = battery;
  state.page = 1;
  const pane = document.getElementById('view-dispositifs');
  if (pane && pane.children.length) update(pane);
}

// ── Point d'entree ─────────────────────────────────────────────────────────────

export async function renderDispositifs(container) {
  container.innerHTML = '<div class="loading">Chargement…</div>';
  // reset (sauf preferences de tri/filtre conservees entre navigations)
  state.page = 1;
  state.selected = null;

  let data;
  try {
    data = await fetchApi('/sentinel/api/trackers?all=1');
  } catch {
    container.innerHTML = '<div class="error-state">Impossible de charger les dispositifs.</div>';
    return;
  }
  state.all = data.trackers || [];

  // Options projet (tri alpha)
  const projOptions = [...new Set(state.all.map(t => t._projectName).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  const projIdByName = {};
  for (const t of state.all) if (t._projectName) projIdByName[t._projectName] = t._projectId;

  container.innerHTML = `
    <div class="disp-toolbar">
      <input type="text" id="disp-search" class="disp-search" placeholder="⌕ Rechercher capteur, projet ou unité…" value="${state.search}" />
      <select id="disp-project" class="dd-filter">
        <option value="">Tous les projets</option>
        ${projOptions.map(p => `<option value="${projIdByName[p]}" ${state.projects.has(projIdByName[p]) ? 'selected' : ''}>${p}</option>`).join('')}
      </select>
    </div>
    <div class="disp-segments">
      <div id="seg-status" class="seg-group"></div>
      <div id="seg-battery" class="seg-group"></div>
    </div>
    <div id="disp-count" class="disp-count"></div>
    <div class="disp-table-wrap">
      <table class="data-table disp-table">
        <thead><tr>
          ${COLS.map(([f, label]) => `<th data-sort="${f}">${label}<span class="sort-ind"></span></th>`).join('')}
        </tr></thead>
        <tbody id="disp-tbody"></tbody>
      </table>
    </div>
    <div class="pagination">
      <span id="disp-pageinfo" class="pagination-info"></span>
      <button id="disp-prev">&laquo; Précédent</button>
      <button id="disp-next">Suivant &raquo;</button>
    </div>
    <div id="disp-backdrop" class="dw-backdrop"></div>
    <aside id="disp-drawer" class="dw-drawer"></aside>
  `;

  // Listeners (attaches une seule fois)
  const search = container.querySelector('#disp-search');
  search.addEventListener('input', () => { state.search = search.value; state.page = 1; update(container); });

  container.querySelector('#disp-project').addEventListener('change', e => {
    state.projects = e.target.value ? new Set([e.target.value]) : new Set();
    state.page = 1; update(container);
  });

  container.querySelector('.disp-segments').addEventListener('click', e => {
    const btn = e.target.closest('.seg-chip');
    if (!btn) return;
    state[btn.dataset.group] = btn.dataset.value;
    state.page = 1; update(container);
  });

  container.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const f = th.dataset.sort;
      if (state.sort === f) state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      else { state.sort = f; state.dir = 'desc'; }
      update(container);
    });
  });

  container.querySelector('#disp-prev').addEventListener('click', () => { state.page--; update(container); });
  container.querySelector('#disp-next').addEventListener('click', () => { state.page++; update(container); });
  container.querySelector('#disp-backdrop').addEventListener('click', () => closeDrawer(container));

  update(container);
}
