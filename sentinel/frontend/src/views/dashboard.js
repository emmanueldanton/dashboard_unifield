import { fetchApi } from '../api.js';

function kpiCard(label, value, sub = '', mod = '') {
  return `<div class="kpi-card ${mod}">
    <div class="kpi-label">${label}</div>
    <div class="kpi-value">${value}</div>
    ${sub ? `<div class="kpi-sub" style="font-size:12px;color:var(--text-muted);margin-top:6px">${sub}</div>` : ''}
  </div>`;
}

function connColor(pct) {
  if (pct >= 80) return 'accent';
  if (pct >= 50) return 'warning';
  return 'danger';
}

// ── Section Urgences (port de ui/tabs/urgences.py) ─────────────────────────────

function fmtSince(secs) {
  if (secs == null || secs < 0) return 'jamais';
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}min`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h`;
  return `${Math.floor(secs / 86400)}j`;
}

function fmtLocal(iso, tz) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      timeZone: tz || 'UTC', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    }).format(d);
  } catch { return d.toLocaleString('fr-FR'); }
}

function battCell(status, volt) {
  const v = (typeof volt === 'number' && volt > 0) ? `${volt.toFixed(2)}V` : '';
  if (status === 'faible') return `<span class="batt-pill batt-low">${v || 'Faible'} ⚠</span>`;
  if (status === 'ok') return `<span class="batt-pill batt-ok">${v || 'OK'}</span>`;
  return `<span class="batt-pill batt-unknown">Inconnu</span>`;
}

function trackerTable(trackers) {
  const rows = trackers.map(t => `<tr>
    <td class="cell-strong">${t.name}</td>
    <td>${t.projectName}<span class="cell-sub"> · ${t.unitName}</span></td>
    <td>${battCell(t.batteryStatus, t.batteryVolt)}</td>
    <td>${fmtSince(t.lastSeenSeconds)}<span class="cell-sub"> · ${fmtLocal(t.lastUpdate, t.projectTz)}</span></td>
  </tr>`).join('');
  return `<table class="data-table"><thead><tr>
    <th>Capteur</th><th>Projet · Unité</th><th>Batterie</th><th>Dernière activité</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

function endingTable(projects) {
  const rows = projects.map(p => `<tr>
    <td class="cell-strong">${p.projet}</td><td>${p.dateFin}</td><td>${p.joursRestants} j</td><td>${p.capteurs}</td>
  </tr>`).join('');
  return `<table class="data-table"><thead><tr>
    <th>Projet</th><th>Date de fin</th><th>Jours restants</th><th>Capteurs</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

function anomalieTable(projects) {
  const rows = projects.map(p => `<tr>
    <td class="cell-strong">${p.projet}</td><td>${p.type}</td><td>${p.dateFin}</td><td>${p.capteurs}</td>
  </tr>`).join('');
  return `<table class="data-table"><thead><tr>
    <th>Projet</th><th>Type</th><th>Date fin</th><th>Capteurs</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

function urgSection(title, count, contentHtml, emptyMsg) {
  const tone = count > 0 ? 'warn' : 'ok';
  const body = count > 0 ? contentHtml : `<div class="banner ok">✓ ${emptyMsg}</div>`;
  return `<details class="urg-section">
    <summary class="urg-summary urg-${tone}">
      <span class="urg-caret">▶</span>
      <span class="urg-title">${title}</span>
      <span class="urg-count">${count}</span>
    </summary>
    <div class="urg-body">${body}</div>
  </details>`;
}

function renderUrgences(u) {
  const s = u.sections;
  const ok = u.totalUrgences === 0;
  return `
    <div class="banner ${ok ? 'ok' : 'danger'}">
      ${ok ? '✓ Aucune urgence — tous les systèmes sont opérationnels.'
           : `⚠ ${u.totalUrgences} alerte(s) nécessitent votre attention`}
    </div>
    <div class="urg-list">
      ${urgSection('Capteurs inactifs pendant horaire', s.inactifsHoraire.count, trackerTable(s.inactifsHoraire.trackers), 'Tous les capteurs actifs pendant les heures prévues.')}
      ${urgSection('Capteurs actifs hors horaire', s.actifsHorsHoraire.count, trackerTable(s.actifsHorsHoraire.trackers), 'Aucun capteur actif hors des heures prévues.')}
      ${urgSection('Batterie faible', s.batterieFaible.count, trackerTable(s.batterieFaible.trackers), 'Toutes les batteries sont au-dessus du seuil.')}
      ${urgSection('Batterie inconnue', s.batterieInconnue.count, trackerTable(s.batterieInconnue.trackers), 'Aucun capteur avec tension inconnue.')}
      ${urgSection('Peson inconnu', s.pesonInconnu.count, trackerTable(s.pesonInconnu.trackers), 'Tous les pesons transmettent des données.')}
      ${urgSection('Projets bientôt terminés', s.projetsBientotTermines.count, endingTable(s.projetsBientotTermines.projects), 'Aucun projet ne se termine dans les prochains jours.')}
      ${urgSection('Projets terminés encore actifs', s.projetsTerminesActifs.count, anomalieTable(s.projetsTerminesActifs.projects), 'Aucun projet terminé avec capteurs encore actifs.')}
    </div>`;
}

function kpiGridHtml(kpis) {
  return `
    ${kpiCard('Projets actifs', kpis.activeProjects,
      `lastUpdate &lt; ${kpis.activityWindowSeconds}s au dernier chargement · ${kpis.totalProjects} projets en cours`,
      kpis.activeProjects > 0 ? 'accent' : '')}
    ${kpiCard('Fin imminente', kpis.endingProjects,
      `Dans les ${kpis.endingDays} prochains jours`,
      kpis.endingProjects > 0 ? 'warning' : '')}
    ${kpiCard('Projets terminés', kpis.pastProjects,
      'endDate dépassée, non archivés',
      kpis.pastProjects > 0 ? 'warning' : '')}
    ${kpiCard('Dispositifs connectés', kpis.connected,
      `${kpis.connectedPct}% du parc · ${kpis.totalTrackers} au total`,
      connColor(kpis.connectedPct))}
    ${kpiCard('Batterie faible', kpis.batteryLow,
      `Seuil &lt; ${kpis.batteryThreshold}V`,
      kpis.batteryLow > 0 ? 'warning' : '')}`;
}

// Met a jour la zone urgences en preservant les sections <details> ouvertes.
function fillUrgences(zone, urgencesData) {
  const prevOpen = [...zone.querySelectorAll('details')].map(d => d.open);
  zone.innerHTML = renderUrgences(urgencesData);
  const details = zone.querySelectorAll('details');
  prevOpen.forEach((open, i) => { if (details[i]) details[i].open = open; });
}

function fmtUpdated(loadedAt) {
  return loadedAt ? new Date(loadedAt).toLocaleTimeString('fr-FR') : '-';
}

// Rafraichissement non destructif : met a jour KPIs, urgences (sections ouvertes
// preservees) et horodatage, sans reconstruire le DOM ni reinitialiser le scroll.
export async function refreshDashboard() {
  if (!document.getElementById('kpi-zone')) return;
  let kpis, urgencesData;
  try {
    [kpis, urgencesData] = await Promise.all([
      fetchApi('/sentinel/api/kpis'),
      fetchApi('/sentinel/api/urgences'),
    ]);
  } catch { return; }

  const kpiZone = document.getElementById('kpi-zone');
  if (!kpiZone) return;
  kpiZone.innerHTML = kpiGridHtml(kpis);

  const urgZone = document.getElementById('urgences-zone');
  if (urgZone) fillUrgences(urgZone, urgencesData);

  const upd = document.getElementById('dashboard-updated');
  if (upd) upd.textContent = `Dernière mise à jour : ${fmtUpdated(kpis.loadedAt)}`;
}

export async function renderDashboard(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';

  const [kpis, urgencesData] = await Promise.all([
    fetchApi('/sentinel/api/kpis'),
    fetchApi('/sentinel/api/urgences'),
  ]);

  container.innerHTML = `
    <div id="kpi-zone" class="kpi-grid">${kpiGridHtml(kpis)}</div>

    <div class="panel">
      <div class="panel-title">Urgences</div>
      <div id="urgences-zone">${renderUrgences(urgencesData)}</div>
    </div>

    <div id="dashboard-updated" style="color:var(--text-muted);font-size:12px;text-align:right">
      Dernière mise à jour : ${fmtUpdated(kpis.loadedAt)}
    </div>
  `;
}
