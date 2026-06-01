'use strict';
const { Router } = require('express');
const { getData } = require('../db/cache');
const { filterData } = require('../lib/flags');
const { computeSegments } = require('../lib/segments');
const { checkScheduleAnomalies } = require('../lib/schedule');

const router = Router();

const ACTIVITY_WINDOW_SECONDS = 60;
const ENDING_SOON_DAYS = 30;
const PAST_DAYS = 10;
const BATTERY_WARNING_THRESHOLD = 3.5;
const RECENT_SECONDS = 86400; // 24h

function msgOf(t) {
  const lt = t.lastTrack || {};
  return (lt.message && typeof lt.message === 'object') ? lt.message : {};
}

// Ligne capteur pour affichage (sous-ensemble de build_tracker_rows)
function trackerRow(t) {
  const msg = msgOf(t);
  const n = v => (typeof v === 'number' && !Number.isNaN(v) ? v : null);
  return {
    name:            t.name || '?',
    projectName:     t._project_name || t._projectName || '-',
    unitName:        t._unit_name || '-',
    projectTz:       t._project_tz || 'UTC',
    batteryVolt:     t._battery_volt ?? t._batteryVolt ?? -1,
    batteryStatus:   t._battery_status || t._batteryStatus || 'inconnu',
    lastSeenSeconds: t._last_seen_seconds ?? t._lastSeenSeconds ?? -1,
    lastUpdate:      t.lastUpdate || null,
    temperature:     n(msg.temperature),
    weight:          n(msg.weight),
  };
}

function fmtDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(d);
}

router.get('/', async (req, res) => {
  try {
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    const data = filterData(cached);
    const { projects, trackers, project_data } = data;
    const now = new Date();
    const bt = BATTERY_WARNING_THRESHOLD;

    const segs = computeSegments(projects, project_data, now,
      ACTIVITY_WINDOW_SECONDS, ENDING_SOON_DAYS, PAST_DAYS);

    // Batterie faible : faible ET (connecte OU vu < 24h)
    const batteryLow = trackers.filter(t =>
      (t._battery_status || t._batteryStatus) === 'faible' &&
      (t._is_connected || t._isConnected || (t._last_seen_seconds >= 0 && t._last_seen_seconds < RECENT_SECONDS)));

    // Batterie inconnue : statut inconnu ET champ battery_volt present dans le message
    const batteryUnk = trackers.filter(t =>
      (t._battery_status || t._batteryStatus) === 'inconnu' && ('battery_volt' in msgOf(t)));

    // Peson inconnu : weight present mais invalide ET (connecte OU vu < 24h)
    const weightUnk = trackers.filter(t =>
      t._weight_status === 'inconnu' && ('weight' in msgOf(t)) &&
      (t._is_connected || t._isConnected || (t._last_seen_seconds >= 0 && t._last_seen_seconds < RECENT_SECONDS)));

    // Anomalies horaires sur les projets en cours + recemment termines
    const horsSchedule = [];
    const manquants = [];
    for (const p of [...segs.total, ...segs.past]) {
      const pd = project_data[p.id] || {};
      const trkrs = pd.trackers || [];
      const tz = pd.timezone || p.timezone || 'UTC';
      const [hs, mq] = checkScheduleAnomalies(trkrs, p.schedule, now, tz);
      horsSchedule.push(...hs);
      manquants.push(...mq);
    }

    // Projets bientot termines (segs.ending)
    const endingProjects = segs.ending.map(p => {
      const end = p.endDate ? new Date(p.endDate) : null;
      const joursRestants = end && !Number.isNaN(end.getTime())
        ? Math.floor((end.getTime() - now.getTime()) / 86400000) : '?';
      return {
        projet:        p.name || '?',
        dateFin:       fmtDate(p.endDate),
        joursRestants,
        capteurs:      (project_data[p.id] || {}).trackers?.length || 0,
      };
    });

    // Projets termines encore actifs (segs.anomalies)
    const anomalieProjects = segs.anomalies.map(p => ({
      projet:   p.name || '?',
      type:     p.type || '?',
      dateFin:  fmtDate(p.endDate),
      capteurs: (project_data[p.id] || {}).trackers?.length || 0,
    }));

    // nb_urg = batteryLow + ending + hors + manquants + anomalies (port exact)
    const totalUrgences = batteryLow.length + endingProjects.length +
      horsSchedule.length + manquants.length + anomalieProjects.length;

    res.json({
      totalUrgences,
      sections: {
        inactifsHoraire:        { count: manquants.length,    trackers: manquants.map(trackerRow) },
        actifsHorsHoraire:      { count: horsSchedule.length,  trackers: horsSchedule.map(trackerRow) },
        batterieFaible:         { count: batteryLow.length,    trackers: batteryLow.map(trackerRow) },
        batterieInconnue:       { count: batteryUnk.length,    trackers: batteryUnk.map(trackerRow) },
        pesonInconnu:           { count: weightUnk.length,     trackers: weightUnk.map(trackerRow) },
        projetsBientotTermines: { count: endingProjects.length, projects: endingProjects },
        projetsTerminesActifs:  { count: anomalieProjects.length, projects: anomalieProjects },
      },
    });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'api_error', path: '/api/urgences', detail: err.message }));
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
