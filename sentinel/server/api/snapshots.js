'use strict';
const { Router } = require('express');
const { getSentinelDb } = require('../db/mongo');
const { ObjectId } = require('mongodb');

const router = Router();

const RANGE_MAP = { '6h': 6, '24h': 24, '7d': 168 };

router.get('/', async (req, res) => {
  const range = RANGE_MAP[req.query.range] ? req.query.range : '24h';
  const hours = RANGE_MAP[range];
  const since = new Date(Date.now() - hours * 3600 * 1000);

  const filter = { ts: { $gte: since } };
  if (req.query.project) {
    filter.project = req.query.project;
  } else {
    filter.project = null;
  }

  try {
    const db = await getSentinelDb();
    const snapshots = await db.collection('snapshots')
      .find(filter, { projection: { _id: 0, ts: 1, connected: 1, disconnected: 1, battery_low: 1, project: 1 } })
      .sort({ ts: 1 })
      .toArray();

    res.json({ snapshots, range });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'api_error', path: '/api/snapshots', detail: err.message }));
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
