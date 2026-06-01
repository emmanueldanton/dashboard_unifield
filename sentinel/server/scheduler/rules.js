'use strict';

const DEFAULT_RULES = [
  { name: 'battery_low',    field: '_batteryVolt',     operator: '<',  threshold: 3.5,  severity: 'warning',  enabled: true, description: 'Batterie faible' },
  { name: 'offline',        field: '_lastSeenSeconds', operator: '>',  threshold: 7200, severity: 'critical', enabled: true, description: 'Tracker hors ligne depuis 2h' },
  { name: 'project_ending', field: 'daysToEnd',        operator: '<=', threshold: 7,    severity: 'warning',  enabled: true, description: 'Projet se terminant dans 7 jours' },

];

async function loadRulesFromDb(db) {
  try {
    const rules = await db.collection('alert_rules').find({ enabled: true }).toArray();
    if (rules.length > 0) return { rules, source: 'db' };
  } catch {
    // fall through to defaults
  }
  return { rules: DEFAULT_RULES, source: 'default' };
}

module.exports = { DEFAULT_RULES, loadRulesFromDb };
