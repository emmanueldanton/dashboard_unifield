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
      <td>${a.rule}</td>
      <td>${a.trackerName}</td>
      <td>${a.projectName || '-'}</td>
      <td style="color:var(--text-muted);font-size:12px">${a.message}</td>
    </tr>`).join('');

  const rulesForm = rules.map(rule => `
    <div class="form-group" data-rule-id="${rule._id || rule.name}">
      <label>${rule.description || rule.name} (${rule.name})</label>
      <div style="display:flex;align-items:center;gap:12px">
        <span style="color:var(--text-muted);font-size:12px">${rule.field} ${rule.operator}</span>
        <input type="number" step="0.1" value="${rule.threshold}" ${isAdmin ? '' : 'disabled'}
          class="rule-threshold" data-id="${rule._id || ''}" style="width:100px" />
        <span class="badge badge-${rule.severity === 'critical' ? 'critical' : 'warning'}">${sevLabel(rule.severity)}</span>
        ${isAdmin ? `<button class="btn-primary btn-save-rule" data-id="${rule._id || ''}">Enregistrer</button>` : ''}
      </div>
    </div>`).join('');

  container.innerHTML = `
    <div class="panel" style="margin-bottom:24px">
      <div class="panel-title">Etat du scheduler</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px">
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Statut</div>
          <div style="font-weight:600;color:${isRunning ? 'var(--accent)' : 'var(--text-muted)'}">${isRunning ? 'En cours...' : 'En attente'}</div>

        </div>
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Dernier cycle</div>
          <div style="font-size:13px">${fmtDate(lastCycle)}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Prochain cycle</div>
          <div style="font-size:13px">${fmtDate(nextCycle)}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Alertes actives</div>
          <div style="font-weight:600;color:${activeAlerts > 0 ? 'var(--danger)' : 'var(--accent)'}">${activeAlerts}</div>
        </div>
      </div>
    </div>

    <div class="panel" style="margin-bottom:24px">
      <div class="panel-title">
        Configuration des regles
        <span style="font-weight:normal;color:var(--text-muted);font-size:11px;margin-left:8px">(source: ${source})</span>
        ${!isAdmin ? '<span style="font-weight:normal;color:var(--text-muted);font-size:11px;margin-left:8px">- lecture seule (role admin requis)</span>' : ''}
      </div>
      <div id="rules-form">${rulesForm}</div>
    </div>

    <div class="panel">
      <div class="panel-title">Historique des alertes (${total} total)</div>
      ${alerts.length === 0 ? '<div class="empty-state">Aucune alerte enregistree.</div>' : `
      <div style="overflow-x:auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>Date</th><th>Severite</th><th>Regle</th>
              <th>Tracker</th><th>Projet</th><th>Message</th>
            </tr>
          </thead>
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
          btn.textContent = 'Enregistre';
          setTimeout(() => { btn.textContent = 'Enregistrer'; btn.disabled = false; }, 2000);
        } catch (err) {
          btn.textContent = 'Erreur';
          btn.disabled = false;
        }
      });
    });
  }
}
