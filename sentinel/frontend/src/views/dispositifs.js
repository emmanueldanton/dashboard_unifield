import { fetchApi } from '../api.js';

let state = { page: 1, connected: '', battery: '', project: '', sort: '_healthScore', dir: 'desc', projects: [] };

function dotStatus(isConnected) {
  return isConnected
    ? '<span class="dot dot-green"></span>Connecté'
    : '<span class="dot dot-red"></span>Déconnecté';
}

function battBadge(status) {
  if (status === 'ok') return '<span style="color:var(--accent)">OK</span>';
  if (status === 'faible') return '<span style="color:var(--warning)">Faible</span>';
  return '<span style="color:var(--text-muted)">Inconnu</span>';
}


function formatSince(secs) {
  if (secs < 0) return 'Jamais';
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}min`;
  return `${Math.floor(secs / 3600)}h${Math.floor((secs % 3600) / 60)}min`;
}

async function load(container) {
  const params = new URLSearchParams({ page: state.page, limit: 50 });
  if (state.connected !== '') params.set('connected', state.connected);
  if (state.battery) params.set('battery', state.battery);
  if (state.project) params.set('project', state.project);

  const data = await fetchApi(`/sentinel/api/trackers?${params}`);
  renderTable(container, data);
}

function renderTable(container, data) {
  const { trackers, total, page, limit } = data;
  const totalPages = Math.ceil(total / limit);

  const projectOptions = state.projects.map(p =>
    `<option value="${p._id}" ${state.project === p._id ? 'selected' : ''}>${p.name}</option>`
  ).join('');

  const col = (field, label) => {
    const icon = state.sort === field ? (state.dir === 'asc' ? ' ^' : ' v') : '';
    return `<th data-sort="${field}">${label}${icon}</th>`;
  };

  const rows = trackers.map(t => `
    <tr>
      <td>${t.name}</td>
      <td>${t._projectName || '<span style="color:var(--text-muted)">-</span>'}</td>
      <td>${dotStatus(t._isConnected)}</td>
      <td>${battBadge(t._batteryStatus)} ${t._batteryVolt > 0 ? `(${t._batteryVolt.toFixed(2)}V)` : ''}</td>
      <td>${formatSince(t._lastSeenSeconds)}</td>
      <td>
        <div style="display:flex;align-items:center;gap:8px">
          <div style="flex:1;height:4px;background:var(--border);border-radius:2px;max-width:80px">
            <div style="width:${t._healthScore}%;height:4px;background:${t._healthScore > 70 ? 'var(--accent)' : t._healthScore > 40 ? 'var(--warning)' : 'var(--danger)'};border-radius:2px"></div>
          </div>
          <span style="font-size:12px;color:var(--text-muted)">${t._healthScore}</span>
        </div>
      </td>
    </tr>`).join('');

  const tbody = container.querySelector('tbody');
  if (tbody) {
    tbody.innerHTML = rows || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">Aucun résultat.</td></tr>';
    container.querySelector('.pagination-info').textContent = `${(page - 1) * limit + 1}-${Math.min(page * limit, total)} sur ${total}`;
    container.querySelector('.btn-prev').disabled = page <= 1;
    container.querySelector('.btn-next').disabled = page >= totalPages;
    return;
  }

  container.innerHTML = `
    <div class="filter-bar">
      <select id="filter-connected">
        <option value="">Connexion: tous</option>
        <option value="true" ${state.connected === 'true' ? 'selected' : ''}>Connectés</option>
        <option value="false" ${state.connected === 'false' ? 'selected' : ''}>Déconnectés</option>
      </select>
      <select id="filter-battery">
        <option value="">Batterie: tous</option>
        <option value="ok" ${state.battery === 'ok' ? 'selected' : ''}>OK</option>
        <option value="faible" ${state.battery === 'faible' ? 'selected' : ''}>Faible</option>
        <option value="inconnu" ${state.battery === 'inconnu' ? 'selected' : ''}>Inconnu</option>
      </select>
      <select id="filter-project">
        <option value="">Projet: tous</option>
        ${projectOptions}
      </select>
    </div>
    <div style="overflow-x:auto">
      <table class="data-table">
        <thead>
          <tr>
            ${col('name', 'Nom')}
            ${col('_projectName', 'Projet')}
            ${col('_isConnected', 'Connexion')}
            ${col('_batteryStatus', 'Batterie')}
            ${col('_lastSeenSeconds', 'Derniere comm.')}
            ${col('_healthScore', 'Score santé')}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="pagination">
      <span class="pagination-info">${(page - 1) * limit + 1}-${Math.min(page * limit, total)} sur ${total}</span>
      <button class="btn-prev" ${page <= 1 ? 'disabled' : ''}>&laquo; Précédent</button>
      <button class="btn-next" ${page >= totalPages ? 'disabled' : ''}>Suivant &raquo;</button>
    </div>
  `;

  container.querySelector('#filter-connected').addEventListener('change', e => { state.connected = e.target.value; state.page = 1; load(container); });
  container.querySelector('#filter-battery').addEventListener('change', e => { state.battery = e.target.value; state.page = 1; load(container); });
  container.querySelector('#filter-project').addEventListener('change', e => { state.project = e.target.value; state.page = 1; load(container); });

  container.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const field = th.dataset.sort;
      if (state.sort === field) state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      else { state.sort = field; state.dir = 'desc'; }
      load(container);
    });
  });

  container.querySelector('.btn-prev').addEventListener('click', () => { state.page--; load(container); });
  container.querySelector('.btn-next').addEventListener('click', () => { state.page++; load(container); });
}

export async function renderDispositifs(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';
  const projectsData = await fetchApi('/sentinel/api/projects');
  state.projects = projectsData.projects || [];
  await load(container);
}
