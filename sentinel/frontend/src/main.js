import { fetchApi } from './api.js';
import { renderDashboard } from './views/dashboard.js';
import { renderDispositifs } from './views/dispositifs.js';
import { renderProjets } from './views/projets.js';
import { renderAlertes } from './views/alertes.js';

let currentView = 'dashboard';
let refreshTimer = null;
let currentUser = null;

const VIEWS = {
  dashboard: renderDashboard,
  dispositifs: renderDispositifs,
  projets: renderProjets,
  alertes: renderAlertes,
};

document.addEventListener('sentinel:unauthorized', () => {
  window.location.href = '/sentinel/auth/login';
});

document.addEventListener('sentinel:forbidden', () => {
  document.getElementById('content').innerHTML =
    '<div class="error-state">Acces refuse - role insuffisant pour acceder a cette ressource.</div>';
});

async function checkAuth() {
  try {
    const me = await fetchApi('/sentinel/auth/me');
    currentUser = me;
    const el = document.getElementById('header-user');
    if (el) el.textContent = me.displayName || me.email;
    return me;
  } catch (err) {
    if (err.status === 401) {
      window.location.href = '/sentinel/auth/login';
    } else if (err.status === 403) {
      document.getElementById('content').innerHTML =
        '<div class="error-state">Acces refuse - aucun role Sentinel valide.</div>';
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

  const content = document.getElementById('content');
  content.innerHTML = '<div class="loading">Chargement...</div>';

  try {
    await VIEWS[view](content, currentUser);
  } catch (err) {
    if (err.code !== 'UNAUTHORIZED' && err.code !== 'FORBIDDEN') {
      content.innerHTML = `<div class="error-state">Erreur: ${err.message}</div>`;
    }
  }

  if (view === 'dashboard') {
    refreshTimer = setInterval(() => navigate('dashboard'), 30000);
  }
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.view));
});

(async function init() {
  try {
    await checkAuth();
    const hash = location.hash.replace('#', '') || 'dashboard';
    const view = VIEWS[hash] ? hash : 'dashboard';
    await navigate(view);
  } catch {
    // auth redirect or error display already handled
  }
})();
