import { fetchApi } from '../api.js';

const ICONS = {
  projects:  `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 4a2 2 0 012-2h4a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V4zm10-2a2 2 0 012-2h2a2 2 0 012 2v12a2 2 0 01-2 2h-2a2 2 0 01-2-2V2z"/></svg>`,
  ending:    `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm1 9H9V5h2v6zm0 2H9v2h2v-2z"/></svg>`,
  done:      `<svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>`,
  signal:    `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zm6-4a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zm6-3a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z"/></svg>`,
  battery:   `<svg viewBox="0 0 20 20" fill="currentColor"><path d="M2 7a2 2 0 012-2h11a2 2 0 012 2v2h.5a.5.5 0 01.5.5v1a.5.5 0 01-.5.5H17v2a2 2 0 01-2 2H4a2 2 0 01-2-2V7z"/></svg>`,
};

function kpiCard(icon, label, value, sub = '', mod = '', nav = null, extra = '') {
  const navAttr = nav ? ` data-nav='${JSON.stringify(nav)}'` : '';
  return `<div class="kpi-card kpi-card--${mod || 'default'}"${navAttr}>
    <div class="kpi-head">
      <span class="kpi-icon kpi-icon--${mod || 'default'}">${icon}</span>
      <span class="kpi-label">${label}</span>
    </div>
    <div class="kpi-value">${value}</div>
    ${extra}
    ${sub ? `<div class="kpi-sub">${sub}</div>` : ''}
  </div>`;
}

function bindKpiNav(container) {
  container.querySelectorAll('[data-nav]').forEach(el => {
    el.style.cursor = 'pointer';
    el.addEventListener('click', () => {
      document.dispatchEvent(new CustomEvent('sentinel:navigate', {
        bubbles: true,
        detail: JSON.parse(el.dataset.nav),
      }));
    });
  });
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

function fmtTemp(val) {
  if (val == null || val === '') return '<span class="cell-sub">—</span>';
  const n = parseFloat(val);
  return Number.isNaN(n) ? '<span class="cell-sub">—</span>' : `${n.toFixed(1)}°C`;
}

function trackerTable(trackers) {
  const sorted = [...trackers].sort((a, b) => {
    const sa = a.lastSeenSeconds ?? Infinity;
    const sb = b.lastSeenSeconds ?? Infinity;
    return sa - sb;
  });
  const rows = sorted.map(t => `<tr>
    <td class="cell-strong">${t.name}</td>
    <td>${t.projectName}<span class="cell-sub"> · ${t.unitName}</span></td>
    <td>${battCell(t.batteryStatus, t.batteryVolt)}</td>
    <td class="cell-since">${fmtSince(t.lastSeenSeconds)}</td>
    <td>${fmtTemp(t.temperature)}</td>
    <td class="cell-sub">${fmtLocal(t.lastUpdate, t.projectTz)}</td>
  </tr>`).join('');
  return `<table class="data-table"><thead><tr>
    <th>Capteur</th><th>Projet · Unité</th><th>Batterie</th><th>Depuis</th><th>Temp.</th><th>Vu le</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

function endingTable(projects) {
  const sorted = [...projects].sort((a, b) => (a.joursRestants ?? 999) - (b.joursRestants ?? 999));
  const rows = sorted.map(p => `<tr>
    <td class="cell-strong">${p.projet}</td><td>${p.dateFin}</td><td>${p.joursRestants} j</td><td>${p.capteurs}</td>
  </tr>`).join('');
  return `<table class="data-table"><thead><tr>
    <th>Projet</th><th>Date de fin</th><th>Jours restants</th><th>Capteurs</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

function anomalieTable(projects) {
  const sorted = [...projects].sort((a, b) => {
    if (!a.dateFin && !b.dateFin) return 0;
    if (!a.dateFin) return 1;
    if (!b.dateFin) return -1;
    return b.dateFin > a.dateFin ? 1 : -1;
  });
  const rows = sorted.map(p => `<tr>
    <td class="cell-strong">${p.projet}</td><td>${p.type}</td><td>${p.dateFin}</td><td>${p.capteurs}</td>
  </tr>`).join('');
  return `<table class="data-table"><thead><tr>
    <th>Projet</th><th>Type</th><th>Date fin</th><th>Capteurs</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

const EMPTY_MSGS = {
  'batt-faible':     'Toutes les batteries sont au-dessus du seuil.',
  'batt-inconnue':   'Aucun capteur avec tension inconnue.',
  'inactif-horaire': 'Tous les capteurs actifs pendant les heures prévues.',
  'hors-horaire':    'Aucun capteur actif hors des heures prévues.',
  'peson':           'Tous les pesons transmettent des données.',
  'fin-imminente':   'Aucun projet ne se termine dans les prochains jours.',
  'termines-actifs': 'Aucun projet terminé avec capteurs encore actifs.',
};

function urgBanner(totalUrgences) {
  if (totalUrgences === 0) {
    return `<div class="urg-banner urg-banner--ok">
      <div class="urg-banner-left">
        <span class="urg-banner-dot"></span>
        <span class="urg-banner-label">SYSTÈME OPÉRATIONNEL</span>
        <span class="urg-banner-sep">·</span>
        <span class="urg-banner-count">Aucune alerte active</span>
      </div>
    </div>`;
  }
  const plural = totalUrgences > 1;
  return `<div class="urg-banner urg-banner--alert">
    <div class="urg-banner-left">
      <svg class="urg-banner-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      <span class="urg-banner-label">URGENCES</span>
      <span class="urg-banner-sep">·</span>
      <span class="urg-banner-count">${totalUrgences} alerte${plural ? 's' : ''} active${plural ? 's' : ''}</span>
    </div>
  </div>`;
}

function buildFaqItems(s) {
  return [
    { id: 'inactif-horaire', label: 'Inactifs pendant horaire', count: s.inactifsHoraire.count,         html: trackerTable(s.inactifsHoraire.trackers),           severity: 'warn'   },
    { id: 'hors-horaire',    label: 'Actifs hors horaire',      count: s.actifsHorsHoraire.count,       html: trackerTable(s.actifsHorsHoraire.trackers),         severity: 'warn'   },
    { id: 'batt-faible',     label: 'Batterie faible',          count: s.batterieFaible.count,          html: trackerTable(s.batterieFaible.trackers),            severity: 'warn'   },
    { id: 'batt-inconnue',   label: 'Batterie inconnue',        count: s.batterieInconnue.count,        html: trackerTable(s.batterieInconnue.trackers),          severity: 'warn'   },
    { id: 'peson',           label: 'Peson inconnu',            count: s.pesonInconnu.count,            html: trackerTable(s.pesonInconnu.trackers),              severity: 'muted'  },
    { id: 'fin-imminente',   label: 'Fin imminente',            count: s.projetsBientotTermines.count,  html: endingTable(s.projetsBientotTermines.projects),     severity: 'warn'   },
    { id: 'termines-actifs', label: 'Terminés encore actifs',   count: s.projetsTerminesActifs.count,   html: anomalieTable(s.projetsTerminesActifs.projects),    severity: 'danger' },
  ];
}

function renderUrgences(u, openIds = []) {
  const s     = u.sections;
  const items = buildFaqItems(s);

  const listHtml = items.map(item => {
    const tone    = item.count > 0 ? item.severity : 'ok';
    const isOpen  = openIds.includes(item.id);
    const body    = item.count > 0
      ? item.html
      : `<div class="urg-empty"><span class="urg-empty-dot"></span>${EMPTY_MSGS[item.id] ?? ''}</div>`;
    const countEl = item.count > 0
      ? `<span class="faq-count faq-count--${tone}">${item.count}</span>`
      : '';

    return `<div class="faq-item faq-item--${tone} ${isOpen ? 'open' : ''}" data-faq="${item.id}">
      <div class="faq-header">
        <span class="faq-title">${item.label}${countEl}</span>
        <span class="faq-toggle">${isOpen ? '−' : '+'}</span>
      </div>
      <div class="faq-body">${body}</div>
    </div>`;
  }).join('');

  return `
    ${urgBanner(u.totalUrgences)}
    <div class="faq-list">${listHtml}</div>`;
}

function bindFaq(zone) {
  const items = [...zone.querySelectorAll('.faq-item')];
  items.forEach(item => {
    item.querySelector('.faq-header').addEventListener('click', () => {
      const wasOpen = item.classList.contains('open');
      items.forEach(i => {
        i.classList.remove('open');
        i.querySelector('.faq-toggle').textContent = '+';
      });
      if (!wasOpen) {
        item.classList.add('open');
        item.querySelector('.faq-toggle').textContent = '−';
      }
    });
  });
}


function kpiGridHtml(kpis) {
  return `
    ${kpiCard(ICONS.projects, 'Projets actifs', kpis.activeProjects,
      `${kpis.totalProjects} projets en cours`,
      kpis.activeProjects > 0 ? 'accent' : 'default',
      { view: 'projets', filter: { status: 'actif' } })}
    ${kpiCard(ICONS.ending, 'Fin imminente', kpis.endingProjects,
      `Dans les ${kpis.endingDays} prochains jours`,
      kpis.endingProjects > 0 ? 'warning' : 'default',
      { view: 'projets', filter: { status: 'se_terminant' } })}
    ${kpiCard(ICONS.done, 'Projets terminés', kpis.pastProjects,
      'endDate dépassée, non archivés',
      kpis.pastProjects > 0 ? 'warning' : 'default',
      { view: 'projets', filter: { status: 'termine' } })}
    ${kpiCard(ICONS.signal, 'Dispositifs connectés', kpis.connected,
      `${kpis.totalTrackers} au total`,
      'accent',
      { view: 'dispositifs', filter: { status: 'connected' } })}
    ${kpiCard(ICONS.battery, 'Batterie faible', kpis.batteryLow,
      `Seuil &lt; ${kpis.batteryThreshold}V`,
      kpis.batteryLow > 0 ? 'warning' : 'default',
      { view: 'dispositifs', filter: { battery: 'faible' } })}`;
}

function scoreColor(s) {
  if (s > 70) return 'var(--accent)';
  if (s > 40) return 'var(--warning)';
  return 'var(--danger)';
}

function worstProjectsWidget(projects) {
  if (!projects || projects.length === 0) return '';
  const rows = projects.map(p => {
    const color = scoreColor(p.score);
    const nav   = JSON.stringify({ view: 'projets', filter: { status: 'all', search: p.name } });
    const since = p.lastActivity ? fmtSince(Math.floor((Date.now() - new Date(p.lastActivity)) / 1000)) : '—';
    return `<div class="wp-row" data-nav='${nav}'>
      <div class="wp-left">
        <span class="wp-name">${p.name}</span>
        <span class="wp-since">Actif ${since}</span>
      </div>
      <div class="wp-right">
        <div class="wp-bar-track"><div class="wp-bar-fill" style="width:${p.score}%;background:${color}"></div></div>
        <span class="wp-score" style="color:${color}">${p.score}%</span>
      </div>
    </div>`;
  }).join('');
  return `<div class="panel wp-panel">
    <div class="panel-header">
      <span class="panel-title">Projets dégradés</span>
      <span class="wp-hint">Actifs dans les 24h · score le plus bas</span>
    </div>
    <div class="wp-list">${rows}</div>
  </div>`;
}

function fillUrgences(zone, urgencesData) {
  const openIds = [...zone.querySelectorAll('.faq-item.open')].map(el => el.dataset.faq);
  zone.innerHTML = renderUrgences(urgencesData, openIds);
  bindFaq(zone);
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

  const wpZone = document.getElementById('wp-zone');
  if (wpZone) { wpZone.innerHTML = worstProjectsWidget(kpis.worstProjects); bindKpiNav(wpZone); }

  const urgZone = document.getElementById('urgences-zone');
  if (urgZone) fillUrgences(urgZone, urgencesData);

  const upd = document.getElementById('dashboard-updated');
  if (upd) upd.textContent = `Mis à jour ${fmtUpdated(kpis.loadedAt)}`;
}

export async function renderDashboard(container) {
  container.innerHTML = '<div class="loading">Chargement...</div>';

  const [kpis, urgencesData] = await Promise.all([
    fetchApi('/sentinel/api/kpis'),
    fetchApi('/sentinel/api/urgences'),
  ]);

  container.innerHTML = `
    <div id="kpi-zone" class="kpi-grid">${kpiGridHtml(kpis)}</div>
    <div id="wp-zone">${worstProjectsWidget(kpis.worstProjects)}</div>
    <div class="panel">
      <div id="urgences-zone">${renderUrgences(urgencesData, [])}</div>
    </div>
  `;

  bindKpiNav(container);
  const urgZoneInit = container.querySelector('#urgences-zone');
  if (urgZoneInit) bindFaq(urgZoneInit);
}
