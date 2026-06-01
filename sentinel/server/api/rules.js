'use strict';
const { Router } = require('express');
const { getDb } = require('../db/mongo');
const { DEFAULT_RULES } = require('../scheduler/rules');
const { ObjectId } = require('mongodb');

const router = Router();

const MUTABLE_FIELDS = new Set(['threshold', 'severity', 'enabled', 'description']);

router.get('/', async (req, res) => {
  try {
    const db = await getDb();
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

  let oid;
  try { oid = new ObjectId(req.params.id); } catch {
    return res.status(404).json({ error: 'Regle non trouvee', code: 'NOT_FOUND' });
  }

  const update = {};
  for (const [key, val] of Object.entries(req.body)) {
    if (MUTABLE_FIELDS.has(key)) update[key] = val;
  }

  if (Object.keys(update).length === 0) {
    return res.status(400).json({ error: 'Aucun champ modifiable fourni', code: 'BAD_REQUEST' });

  }

  try {
    const db = await getDb();
    const result = await db.collection('alert_rules').findOneAndUpdate(
      { _id: oid },
      { $set: update },
      { returnDocument: 'after' }
    );
    if (!result) return res.status(404).json({ error: 'Regle non trouvee', code: 'NOT_FOUND' });

    console.log(JSON.stringify({
      ts: new Date().toISOString(),
      event: 'rule_updated',
      rule: result.name,
      user: session.email,
      changes: update,
    }));

    res.json(result);
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
