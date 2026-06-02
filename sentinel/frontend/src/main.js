import './styles/z42.css';
import { fetchApi } from './api.js';
import { renderDashboard, refreshDashboard } from './views/dashboard.js';
import { renderDispositifs, applyFilter as filterDispositifs } from './views/dispositifs.js';
import { renderProjets, applyFilter as filterProjets } from './views/projets.js';
import { renderAlertes } from './views/alertes.js';

let currentView = 'dashboard';
let refreshTimer = null;
let currentUser = null;

// Vues déjà rendues — on ne re-fetche pas si le DOM est déjà là.
// rendered.clear() + navigate() force un re-rendu complet (ex. : bouton Actualiser).
const rendered = new Set();

const VIEWS = {
  dashboard:   renderDashboard,
  dispositifs: renderDispositifs,
  projets:     renderProjets,
  alertes:     renderAlertes,
};

document.addEventListener('sentinel:unauthorized', () => {
  window.location.href = '/sentinel/auth/login';
});


function fmtUpdated(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

async function refreshStatus() {
  const badge = document.getElementById('header-status');
  const updated = document.getElementById('header-updated');
  if (!badge) return;
  try {
    const s = await fetchApi('/sentinel/api/status');
    if (s.mongoOk) {
      badge.className = 'conn-badge conn-ok';
      badge.innerHTML = '<span class="dot-live"></span> MongoDB OK';
    } else {
      badge.className = 'conn-badge conn-err';
      badge.innerHTML = '<span class="dot-err"></span> MongoDB hors ligne';
    }
    if (updated) updated.textContent = s.loadedAt ? `Dernière MAJ : ${fmtUpdated(s.loadedAt)}` : 'Aucune donnée chargée';
  } catch {
    badge.className = 'conn-badge conn-err';
    badge.innerHTML = '<span class="dot-err"></span> MongoDB hors ligne';
    if (updated) updated.textContent = '';
  }
}

async function checkAuth() {
  try {
    const me = await fetchApi('/sentinel/auth/me');
    currentUser = me;
    const name = me.displayName || me.email || '';
    const el = document.getElementById('header-user');
    if (el) el.textContent = name;
    const av = document.getElementById('header-avatar');
    if (av) av.textContent = name.charAt(0).toUpperCase();
    return me;
  } catch (err) {
    if (err.status === 401) {
      window.location.href = '/sentinel/auth/login';
    } else if (err.status === 403) {
      const pane = document.getElementById('view-dashboard');
      if (pane) pane.innerHTML = '<div class="error-state">Acces refuse — aucun role Sentinel valide.</div>';
    }
    throw err;
  }
}

function setActiveTab(view) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });
}

async function navigate(view) {
  currentView = view;
  setActiveTab(view);
  clearInterval(refreshTimer);

  // Bascule la visibilité — pas de destruction DOM
  document.querySelectorAll('.view-pane').forEach(pane => {
    pane.hidden = (pane.id !== `view-${view}`);
  });

  const pane = document.getElementById(`view-${view}`);

  // Ne re-fetche que si la vue n'a jamais été rendue (ou a été invalidée)
  if (!rendered.has(view)) {
    pane.innerHTML = '<div class="loading">Chargement...</div>';
    try {
      await VIEWS[view](pane, currentUser);
      rendered.add(view);
    } catch (err) {
      rendered.delete(view);
      if (err.code !== 'UNAUTHORIZED' && err.code !== 'FORBIDDEN') {
        pane.innerHTML = `<div class="error-state">Erreur : ${err.message}</div>`;
      }
    }
  }

  if (view === 'dashboard') {
    // Rafraichissement léger toutes les 30 s (sans reconstruction DOM)
    refreshTimer = setInterval(refreshDashboard, 30000);
  }
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.view));
});

// KPI cliquable → navigation avec filtre pré-appliqué
const viewFilters = { dispositifs: filterDispositifs, projets: filterProjets };
document.addEventListener('sentinel:navigate', async ({ detail: { view, filter } = {} }) => {
  if (filter && viewFilters[view]) viewFilters[view](filter);
  await navigate(view);
});

const btnRefresh = document.getElementById('btn-refresh');
if (btnRefresh) {
  btnRefresh.addEventListener('click', async () => {
    if (btnRefresh.disabled) return;
    btnRefresh.disabled = true;
    btnRefresh.textContent = '↺ Actualisation…';
    try {
      await fetchApi('/sentinel/api/cache/refresh', { method: 'POST' });
      rendered.clear(); // invalide toutes les vues — elles re-fetcheront à la prochaine visite
      await refreshStatus();
      await navigate(currentView); // re-rend immédiatement la vue courante
    } catch {
      // erreur déjà affichée par fetchApi ou navigate
    } finally {
      btnRefresh.disabled = false;
      btnRefresh.textContent = '↺ Actualiser';
    }
  });
}

(async function init() {
  try {
    await checkAuth();
    refreshStatus();
    setInterval(refreshStatus, 30000);
    const hash = location.hash.replace('#', '') || 'dashboard';
    const view = VIEWS[hash] ? hash : 'dashboard';
    await navigate(view);
  } catch {
    // redirect ou affichage d'erreur déjà gérés dans checkAuth
  }
})();
