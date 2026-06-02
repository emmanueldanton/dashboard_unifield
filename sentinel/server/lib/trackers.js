'use strict';

// Port de business/trackers.py avec correction du biais de score santé.
//
// Biais identifié : diviser par TOUS les trackers (y compris jamais déployés
// ou abandonnés depuis des mois) donne un score artificiellement bas.
// Fix : seuls les capteurs "opérationnels" entrent dans le dénominateur.

// Fenêtre de référence : capteur non vu depuis > 30j = inactif, exclu du score.
const STALE_TRACKER_DAYS = 30;

function lastSeenSeconds(tracker) {
  if (!tracker.lastUpdate) return -1;
  return Math.floor((Date.now() - new Date(tracker.lastUpdate).getTime()) / 1000);
}

function isConnected(tracker, offlineDelay = 60) {
  const secs = lastSeenSeconds(tracker);
  if (secs < 0) return false;
  return secs < offlineDelay;
}

function batteryVolt(tracker) {
  return tracker.lastTrack?.message?.battery_volt ?? -1;
}

function batteryStatus(tracker, threshold = 3.5) {
  const volt = batteryVolt(tracker);
  if (volt < 0) return 'inconnu';
  return volt < threshold ? 'faible' : 'ok';
}

function weightStatus(tracker) {
  const w = tracker.lastTrack?.message?.weight;
  if (w === undefined || w === null || w < 0) return 'inconnu';
  return 'ok';
}

// Un capteur est "opérationnel" s'il a émis au moins une fois ET dans les N derniers jours.
// Les capteurs jamais déployés (lastUpdate null) ou silencieux depuis longtemps
// ne représentent pas une panne active : ils ne doivent pas biaiser le dénominateur.
function isOperational(tracker, staleDays = STALE_TRACKER_DAYS) {
  const secs = lastSeenSeconds(tracker);
  return secs >= 0 && secs < staleDays * 86400;
}

// Calcule le score santé moyen sur les capteurs opérationnels uniquement.
// Score par capteur : connexion 50 pts + batterie ok 30 pts + peson présent 20 pts.
// Retourne 0 si aucun capteur opérationnel (projet sans signal récent).
function healthScore(trackers, offlineDelay = 60, threshold = 3.5) {
  if (!trackers || !trackers.length) return 0;

  const operational = trackers.filter(t => isOperational(t));
  if (!operational.length) return 0;

  const total = operational.reduce((acc, t) =>
    acc + (isConnected(t, offlineDelay) ? 50 : 0)
        + (batteryStatus(t, threshold) === 'ok' ? 30 : 0)
        + (weightStatus(t) === 'ok' ? 20 : 0), 0);
  return Math.round(total / operational.length);
}

function enrichTracker(t, offlineDelay = 60, threshold = 3.5) {
  t._lastSeenSeconds = lastSeenSeconds(t);
  t._isConnected     = isConnected(t, offlineDelay);
  t._batteryVolt     = batteryVolt(t);
  t._batteryStatus   = batteryStatus(t, threshold);
  t._healthScore     = healthScore([t], offlineDelay, threshold);
}

module.exports = {
  STALE_TRACKER_DAYS,
  isOperational,
  isConnected,
  batteryVolt,
  batteryStatus,
  weightStatus,
  lastSeenSeconds,
  healthScore,
  enrichTracker,
};
