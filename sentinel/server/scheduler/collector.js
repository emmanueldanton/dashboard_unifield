'use strict';
const { loadAllData } = require('../db/loader');
const { filterData } = require('../lib/flags');
const { getSentinelDb } = require('../db/mongo');
const { saveSnapshot } = require('./snapshots');
const { loadRulesFromDb } = require('./rules');
const { evaluate, diff } = require('./engine');
const { sendAlert, writeHistory } = require('./mailer');

async function runCycle(_db, previousState) {
  const ts = new Date().toISOString();
  console.log(JSON.stringify({ ts, event: 'cycle_start' }));
  const start = Date.now();

  try {
    const sdb = await getSentinelDb();
    // filter_data : ne traiter que les trackers reels (parasites + sans donnees exclus),
    // comme le pipeline Python. Evite des milliers de fausses alertes.
    const { trackers } = filterData(await loadAllData());

    const connected = trackers.filter(t => t._isConnected).length;
    const disconnected = trackers.length - connected;
    const battery_low = trackers.filter(t => t._batteryStatus === 'faible').length;

    try {
      await saveSnapshot(sdb, { connected, disconnected, battery_low, project: null });
      console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'snapshot_saved' }));
    } catch (snapErr) {
      console.warn(JSON.stringify({ ts: new Date().toISOString(), event: 'snapshot_skip', detail: snapErr.message }));
    }

    const { rules } = await loadRulesFromDb(sdb);
    const currentAlerts = evaluate(trackers, rules);
    const { newAlerts, resolved } = diff(previousState, currentAlerts);

    if (newAlerts.length > 0) {
      await Promise.all([
        sendAlert(newAlerts),
        writeHistory(sdb, newAlerts),
      ]);
      const byProject = {};
      for (const a of newAlerts) {
        const k = a.projectName || 'Sans projet';
        if (!byProject[k]) byProject[k] = 0;
        byProject[k]++;
      }
      for (const [project, count] of Object.entries(byProject)) {
        console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'alert_sent', count, project }));
      }
    }

    // Update previousState in place
    previousState.clear();
    const currentMap = new Map();
    for (const alert of currentAlerts) {
      if (!currentMap.has(alert.trackerId)) currentMap.set(alert.trackerId, new Set());
      currentMap.get(alert.trackerId).add(alert.rule);
    }
    for (const [k, v] of currentMap) previousState.set(k, v);

    const duration_ms = Date.now() - start;
    console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'cycle_complete', duration_ms, alerts: newAlerts.length }));
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'cycle_error', detail: err.message }));
  }
}

module.exports = { runCycle };
