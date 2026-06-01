'use strict';
const { Router } = require('express');
const { getData } = require('../db/cache');
const { computeSegments } = require('../lib/segments');
const { filterData } = require('../lib/flags');

const router = Router();

// Seuils metier portes depuis config.py (source de verite Python Dash)
const ACTIVITY_WINDOW_SECONDS    = 60;   // fenetre "signal" pour projet actif
const ENDING_SOON_DAYS           = 30;   // "fin imminente"
const PAST_DAYS                  = 10;
const BATTERY_WARNING_THRESHOLD  = 3.5;
const RECENT_BATTERY_SECONDS     = 86400; // batterie faible comptee si vu < 24h

router.get('/', async (req, res) => {
  try {
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    // filter_data : retire les projets parasites + trackers sans donnees
    const data = filterData(cached);
    const { projects, trackers, project_data, loaded_at } = data;
    const now = new Date();

    const segs = computeSegments(
      projects, project_data, now,
      ACTIVITY_WINDOW_SECONDS, ENDING_SOON_DAYS, PAST_DAYS
    );

    // Dispositifs connectes (sur le parc filtre)
    const connected = trackers.filter(t => t._isConnected).length;
    const totalTrackers = trackers.length;
    const disconnected = totalTrackers - connected;
    const connectedPct = totalTrackers ? Math.round((connected / totalTrackers) * 100) : 0;

    // Batterie faible : faible ET (connecte OU vu il y a moins de 24h)
    // (port exact de la condition Python dans update_kpis / render_urgences)
    const batteryLow = trackers.filter(t =>
      t._batteryStatus === 'faible' &&
      (t._isConnected || (t._lastSeenSeconds >= 0 && t._lastSeenSeconds < RECENT_BATTERY_SECONDS))
    ).length;

    res.json({
      // 5 KPIs alignes sur le dashboard Python
      activeProjects:  segs.active.length,
      endingProjects:  segs.ending.length,
      pastProjects:    segs.past.length,
      totalProjects:   segs.total.length,
      connected,
      connectedPct,
      totalTrackers,
      disconnected,
      batteryLow,
      // seuils exposes pour les sous-textes des cartes
      activityWindowSeconds: ACTIVITY_WINDOW_SECONDS,
      endingDays:      ENDING_SOON_DAYS,
      batteryThreshold: BATTERY_WARNING_THRESHOLD,
      loadedAt: loaded_at,
    });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'api_error', path: '/api/kpis', detail: err.message }));
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
