'use strict';
const { Router } = require('express');
const { getDb } = require('../db/mongo');
const { loadAllData } = require('../db/loader');
const { isConnected, batteryStatus } = require('../lib/trackers');
const { isActive } = require('../lib/segments');

const router = Router();

router.get('/', async (req, res) => {
  try {
    const db = await getDb();
    const { projects, trackers, loaded_at } = await loadAllData(db);

    const activeProjects = projects.filter(isActive).length;
    const connected = trackers.filter(t => t._isConnected).length;
    const disconnected = trackers.length - connected;
    const batteryLow = trackers.filter(t => t._batteryStatus === 'faible').length;
    // urgences = trackers offline for more than 2h (7200s)
    const urgences = trackers.filter(t => t._lastSeenSeconds > 7200).length;

    res.json({ activeProjects, connected, disconnected, batteryLow, urgences, loadedAt: loaded_at });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'api_error', path: '/api/kpis', detail: err.message }));
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
