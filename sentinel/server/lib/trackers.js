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

function healthScore(trackers, offlineDelay = 60, threshold = 3.5) {
  if (!trackers || trackers.length === 0) return 0;
  const connected = trackers.filter(t => isConnected(t, offlineDelay)).length;
  const battOk = trackers.filter(t => batteryStatus(t, threshold) === 'ok').length;
  const connScore = Math.round((connected / trackers.length) * 50);
  const battScore = Math.round((battOk / trackers.length) * 30);
  // signal score: proxy - trackers seen in last 5 minutes
  const recent = trackers.filter(t => {
    const s = lastSeenSeconds(t);
    return s >= 0 && s < 300;
  }).length;
  const signalScore = Math.round((recent / trackers.length) * 20);
  return connScore + battScore + signalScore;
}

function enrichTracker(t, offlineDelay = 60, threshold = 3.5) {
  t._lastSeenSeconds = lastSeenSeconds(t);
  t._isConnected = isConnected(t, offlineDelay);
  t._batteryVolt = batteryVolt(t);
  t._batteryStatus = batteryStatus(t, threshold);
  t._healthScore = healthScore([t], offlineDelay, threshold);
}

module.exports = { isConnected, batteryVolt, batteryStatus, lastSeenSeconds, healthScore, enrichTracker };
