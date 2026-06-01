'use strict';
const { Router } = require('express');
const { refresh, getCacheMeta } = require('../db/cache');

const router = Router();

// Force un rechargement immediat du cache MongoDB.
// Protege par le guard auth — tout role peut declencher un refresh.
router.post('/refresh', async (_req, res) => {
  try {
    await refresh();
    const meta = getCacheMeta();
    res.json({
      mongoOk: meta.mongoOk,
      loadedAt: meta.loadedAt ? new Date(meta.loadedAt).toISOString() : null,
      version: meta.version,
    });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'cache_refresh_error', detail: err.message }));
    res.status(503).json({ error: 'Echec du rafraichissement', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
