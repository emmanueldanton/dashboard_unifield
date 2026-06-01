'use strict';

// Port exact de business/trackers.py

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

// Port exact de business/trackers.py weight_status : peson present (weight >= 0).
function weightStatus(tracker) {
  const w = tracker.lastTrack?.message?.weight;
  if (w === undefined || w === null || w < 0) return 'inconnu';
  return 'ok';
}

// Port exact de business/trackers.py health_score :
// somme par tracker (50 connexion + 30 batterie ok + 20 peson present),
// moyenne sur le nombre de trackers, arrondie une seule fois.
function healthScore(trackers, offlineDelay = 60, threshold = 3.5) {
  if (!trackers || trackers.length === 0) return 0;
  const total = trackers.reduce((acc, t) =>
    acc + (isConnected(t, offlineDelay) ? 50 : 0)
        + (batteryStatus(t, threshold) === 'ok' ? 30 : 0)
        + (weightStatus(t) === 'ok' ? 20 : 0), 0);
  return Math.round(total / trackers.length);
}

function enrichTracker(t, offlineDelay = 60, threshold = 3.5) {
  t._lastSeenSeconds = lastSeenSeconds(t);
  t._isConnected = isConnected(t, offlineDelay);
  t._batteryVolt = batteryVolt(t);
  t._batteryStatus = batteryStatus(t, threshold);
  t._healthScore = healthScore([t], offlineDelay, threshold);
}

module.exports = { isConnected, batteryVolt, batteryStatus, weightStatus, lastSeenSeconds, healthScore, enrichTracker };
