'use strict';
const { Router } = require('express');
const { getDb } = require('../db/mongo');
const { loadAllData } = require('../db/loader');

const router = Router();

router.get('/', async (req, res) => {
  const page = Math.max(1, parseInt(req.query.page || '1', 10));
  const limit = Math.min(50, Math.max(1, parseInt(req.query.limit || '50', 10)));

  try {
    const db = await getDb();
    const { trackers } = await loadAllData(db);

    let filtered = trackers;

    if (req.query.connected !== undefined) {
      const want = req.query.connected === 'true';
      filtered = filtered.filter(t => t._isConnected === want);
    }

    if (req.query.battery) {
      const batt = req.query.battery;
      filtered = filtered.filter(t => t._batteryStatus === batt);
    }

    if (req.query.project) {
      filtered = filtered.filter(t => t._projectId === req.query.project);
    }

    filtered.sort((a, b) => b._healthScore - a._healthScore);

    const total = filtered.length;
    const start = (page - 1) * limit;
    const page_items = filtered.slice(start, start + limit).map(t => ({
      _id: t._id,
      name: t.name,
      _projectId: t._projectId,
      _projectName: t._projectName,
      _isConnected: t._isConnected,
      _batteryVolt: t._batteryVolt,
      _batteryStatus: t._batteryStatus,
      _lastSeenSeconds: t._lastSeenSeconds,
      _healthScore: t._healthScore,
    }));

    res.json({ trackers: page_items, total, page, limit });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
