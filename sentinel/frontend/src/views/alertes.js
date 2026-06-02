import { fetchApi } from '../api.js';

export async function renderAlertes(container, user) {
  container.innerHTML = '<div class="loading">Chargement...</div>';

  const [historyData, statusData, rulesData] = await Promise.all([
    fetchApi('/sentinel/api/alert-history'),
    fetchApi('/sentinel/api/alert-status'),
    fetchApi('/sentinel/api/rules'),
  ]);

  const isAdmin = user?.role === 'app:sentinel:admin';
  const { alerts, total } = historyData;
  const { lastCycle, nextCycle, activeAlerts, isRunning } = statusData;
  const { rules, source } = rulesData;

  const fmtDate = iso => iso ? new Date(iso).toLocaleString('fr-FR') : '-';
  const sevLabel = s => s === 'critical' ? 'Critique' : 'Avertissement';

  const alertRows = (alerts || []).map(a => `
    <tr>
      <td>${fmtDate(a.ts)}</td>
      <td><span class="badge badge-${a.severity === 'critical' ? 'critical' : 'warning'}">${sevLabel(a.severity)}</span></td>
      <td class="cell-strong">${a.rule}</td>
      <td>${a.trackerName}</td>
      <td>${a.projectName || '-'}</td>
      <td class="cell-sub">${a.message}</td>
    </tr>`).join('');

  const ruleRows = rules.map(rule => `
    <tr data-rule-id="${rule._id || rule.name}">
      <td>
        <div class="cell-strong">${rule.description || rule.name}</div>
        <div class="cell-sub">${rule.name}</div>
      </td>
      <td class="cell-sub">${rule.field} ${rule.operator}</td>
      <td>
        ${isAdmin
          ? `<input type="number" step="0.1" value="${rule.threshold}"
               class="rule-threshold alert-input" data-id="${rule._id || rule.name}" />`
          : `<span class="dw-stat-value">${rule.threshold}</span>`}
      </td>
      <td><span class="badge badge-${rule.severity === 'critical' ? 'critical' : 'warning'}">${sevLabel(rule.severity)}</span></td>
      ${isAdmin ? `<td><button class="btn-primary btn-save-rule" data-id="${rule._id || rule.name}">Enregistrer</button></td>` : ''}
    </tr>`).join('');

  container.innerHTML = `
    <div class="alert-stat-grid">
      <div class="dw-stat">
        <div class="dw-stat-label">Statut scheduler</div>
        <div class="dw-stat-value ${isRunning ? 'stat-val--accent' : 'stat-val--muted'}">${isRunning ? 'En cours…' : 'En attente'}</div>
      </div>
      <div class="dw-stat">
        <div class="dw-stat-label">Dernier cycle</div>
        <div class="dw-stat-value">${fmtDate(lastCycle)}</div>
      </div>
      <div class="dw-stat">
        <div class="dw-stat-label">Prochain cycle</div>
        <div class="dw-stat-value">${fmtDate(nextCycle)}</div>
      </div>
      <div class="dw-stat">
        <div class="dw-stat-label">Alertes actives</div>
        <div class="dw-stat-value ${activeAlerts > 0 ? 'stat-val--danger' : 'stat-val--accent'}">${activeAlerts}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-header-left">
          <div class="panel-title" style="margin-bottom:0">Configuration des règles</div>
          <span class="panel-updated">source : ${source}</span>
        </div>
        ${!isAdmin ? '<span class="panel-badge panel-badge--warn">Lecture seule</span>' : ''}
      </div>
      ${rules.length === 0
        ? '<div class="empty-state">Aucune règle configurée.</div>'
        : `<div class="disp-table-wrap">
             <table class="data-table">
               <thead><tr>
                 <th>Règle</th><th>Condition</th><th>Seuil</th><th>Sévérité</th>${isAdmin ? '<th></th>' : ''}
               </tr></thead>
               <tbody>${ruleRows}</tbody>
             </table>
           </div>`}
    </div>

    <div class="panel">
      <div class="panel-header">
        <div class="panel-title" style="margin-bottom:0">Historique des alertes</div>
        <span class="panel-badge ${total > 0 ? 'panel-badge--warn' : 'panel-badge--ok'}">${total} total</span>
      </div>
      ${alerts.length === 0
        ? '<div class="empty-state">Aucune alerte enregistrée.</div>'
        : `<div class="disp-table-wrap">
             <table class="data-table">
               <thead><tr>
                 <th>Date</th><th>Sévérité</th><th>Règle</th><th>Capteur</th><th>Projet</th><th>Message</th>
               </tr></thead>
               <tbody>${alertRows}</tbody>
             </table>
           </div>`}
    </div>
  `;

  if (isAdmin) {
    container.querySelectorAll('.btn-save-rule').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.id;
        const input = container.querySelector(`.rule-threshold[data-id="${id}"]`);
        const threshold = parseFloat(input.value);
        if (isNaN(threshold)) return;
        btn.disabled = true;
        try {
          await fetchApi(`/sentinel/api/rules/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ threshold }),
          });
          btn.textContent = 'Enregistré';
          setTimeout(() => { btn.textContent = 'Enregistrer'; btn.disabled = false; }, 2000);
        } catch (err) {
          console.error('[rules] save failed:', err.message, err.status);
          btn.textContent = err.code === 'FORBIDDEN' ? 'Non autorisé' : 'Erreur';
          setTimeout(() => { btn.textContent = 'Enregistrer'; btn.disabled = false; }, 2000);
        }
      });
    });
  }
}
