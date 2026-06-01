'use strict';
const { Router } = require('express');
const { getCacheMeta } = require('../db/cache');

const router = Router();

// Etat du cache MongoDB pour le header : connexion OK + horodatage du dernier
// chargement reussi des donnees (port de is_mongo_ok / last_success_ts cote Python).
router.get('/', (_req, res) => {
  const meta = getCacheMeta();
  res.json({
    mongoOk: meta.mongoOk,
    loadedAt: meta.loadedAt ? new Date(meta.loadedAt).toISOString() : null,
    version: meta.version,
    loading: meta.loading,
  });
});

module.exports = router;
