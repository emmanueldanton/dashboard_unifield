'use strict';
const { Router } = require('express');
const { getSentinelDb } = require('../db/mongo');
const { DEFAULT_RULES } = require('../scheduler/rules');
const { ObjectId } = require('mongodb');

const router = Router();

const MUTABLE_FIELDS = new Set(['threshold', 'severity', 'enabled', 'description']);

router.get('/', async (_req, res) => {
  try {
    const db = await getSentinelDb();
    const rules = await db.collection('alert_rules').find({}).toArray();
    if (rules.length > 0) return res.json({ rules, source: 'db' });
    res.json({ rules: DEFAULT_RULES, source: 'default' });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

router.put('/:id', async (req, res) => {
  const session = req.session;
  if (!session || session.role !== 'app:sentinel:admin') {
    return res.status(403).json({ error: 'Role admin requis', code: 'FORBIDDEN' });
  }

  const update = {};
  for (const [key, val] of Object.entries(req.body)) {
    if (MUTABLE_FIELDS.has(key)) update[key] = val;
  }
  if (Object.keys(update).length === 0) {
    return res.status(400).json({ error: 'Aucun champ modifiable fourni', code: 'BAD_REQUEST' });
  }

  try {
    const db = await getSentinelDb();
    let result;

    let oid;
    try { oid = new ObjectId(req.params.id); } catch { /* id is a rule name, not an ObjectId */ }

    if (oid) {
      // Règle déjà en base — mise à jour par _id
      result = await db.collection('alert_rules').findOneAndUpdate(
        { _id: oid },
        { $set: update },
        { returnDocument: 'after' }
      );
      if (!result) return res.status(404).json({ error: 'Regle non trouvee', code: 'NOT_FOUND' });
    } else {
      // Règle par défaut pas encore persistée — upsert par name
      const name = req.params.id;
      const base = DEFAULT_RULES.find(r => r.name === name);
      if (!base) return res.status(404).json({ error: 'Regle non trouvee', code: 'NOT_FOUND' });
      result = await db.collection('alert_rules').findOneAndUpdate(
        { name },
        { $set: { ...base, ...update } },
        { upsert: true, returnDocument: 'after' }
      );
    }

    if (result) {
      console.log(JSON.stringify({
        ts: new Date().toISOString(),
        event: 'rule_updated',
        rule: result.name,
        user: session.email,
        changes: update,
      }));
    }

    res.json(result || {});
  } catch (err) {
    console.error(JSON.stringify({
      ts: new Date().toISOString(),
      event: 'rule_update_error',
      id: req.params.id,
      detail: err.message,
    }));
    res.status(503).json({ error: err.message, code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
