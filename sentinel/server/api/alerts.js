'use strict';
const { Router } = require('express');
const { getDb } = require('../db/mongo');
const { getSchedulerState } = require('../scheduler/index');

const historyRouter = Router();
const statusRouter = Router();

historyRouter.get('/', async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || '50', 10), 50);
  try {
    const db = await getDb();
    const alerts = await db.collection('alert_history')
      .find({})
      .sort({ ts: -1 })
      .limit(limit)
      .toArray();
    const total = await db.collection('alert_history').countDocuments();
    res.json({ alerts, total });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

statusRouter.get('/', async (req, res) => {
  try {
    const { isRunning, lastCycle, nextCycle } = getSchedulerState();
    const db = await getDb();
    // Count alerts from last cycle window
    const since = lastCycle ? new Date(new Date(lastCycle) - 10 * 60 * 1000) : new Date(0);
    const activeAlerts = await db.collection('alert_history').countDocuments({ ts: { $gte: since } });
    res.json({ lastCycle, nextCycle, activeAlerts, isRunning });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = { historyRouter, statusRouter };
