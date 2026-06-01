'use strict';

const OPS = {
  '<':  (a, b) => a < b,
  '>':  (a, b) => a > b,
  '<=': (a, b) => a <= b,
  '>=': (a, b) => a >= b,
};

function compare(value, operator, threshold) {
  const fn = OPS[operator];
  if (!fn) return false;
  return fn(value, threshold);
}

function evaluate(trackers, rules) {
  const alerts = [];
  for (const tracker of trackers) {
    for (const rule of rules) {
      if (!rule.enabled) continue;
      const value = tracker[rule.field];
      if (value === undefined || value === null) continue;
      // Valeurs sentinelles "donnee absente" (-1) : batterie inconnue ou tracker
      // jamais vu ne doivent PAS declencher d'alerte (semantique business/*.py :
      // battery_status 'inconnu' ignore, offline exige last_seen_seconds >= 0).
      if ((rule.field === '_batteryVolt' || rule.field === '_lastSeenSeconds') && value < 0) continue;
      if (compare(value, rule.operator, rule.threshold)) {
        alerts.push({
          trackerId: tracker._id.toString(),
          trackerName: tracker.name,
          projectId: tracker._projectId || null,
          projectName: tracker._projectName || null,
          rule: rule.name,
          severity: rule.severity,
          message: `Tracker ${tracker.name} - règle ${rule.name} déclenchée (valeur: ${value})`,
        });
      }
    }
  }
  return alerts;
}

function diff(previousState, currentAlerts) {
  // previousState: Map<trackerId, Set<ruleNames>>
  const currentMap = new Map();
  for (const alert of currentAlerts) {
    if (!currentMap.has(alert.trackerId)) currentMap.set(alert.trackerId, new Set());
    currentMap.get(alert.trackerId).add(alert.rule);
  }

  const newAlerts = [];
  for (const alert of currentAlerts) {
    const prev = previousState.get(alert.trackerId);
    if (!prev || !prev.has(alert.rule)) {
      newAlerts.push(alert);
    }
  }

  const resolved = [];
  for (const [trackerId, ruleSet] of previousState) {
    const current = currentMap.get(trackerId);
    for (const rule of ruleSet) {
      if (!current || !current.has(rule)) {
        resolved.push({ trackerId, rule });
      }
    }
  }

  return { newAlerts, resolved };
}

module.exports = { evaluate, diff, compare };
