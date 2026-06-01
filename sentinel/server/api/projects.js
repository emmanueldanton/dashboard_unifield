'use strict';
const { Router } = require('express');
const { getDb } = require('../db/mongo');
const { loadAllData } = require('../db/loader');
const { healthScore } = require('../lib/trackers');
const { projectStatus } = require('../lib/segments');
const { ObjectId } = require('mongodb');

const router = Router();

function enrichProject(project, allTrackers) {
  const projectTrackers = allTrackers.filter(t => t._projectId === project._id.toString());
  return {
    _id: project._id,
    name: project.name,
    code: project.code,
    startDate: project.startDate || null,
    endDate: project.endDate || null,
    archived: project.archived || false,
    _status: projectStatus(project),
    _trackerCount: projectTrackers.length,
    _healthScore: healthScore(projectTrackers),
  };
}

router.get('/', async (req, res) => {
  try {
    const db = await getDb();
    const { projects, trackers } = await loadAllData(db);
    const enriched = projects.map(p => enrichProject(p, trackers));
    res.json({ projects: enriched });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

router.get('/:id', async (req, res) => {
  let oid;
  try { oid = new ObjectId(req.params.id); } catch {
    return res.status(404).json({ error: 'Projet non trouve', code: 'NOT_FOUND' });
  }

  try {
    const db = await getDb();
    const { projects, trackers } = await loadAllData(db);
    const project = projects.find(p => p._id.toString() === oid.toString());
    if (!project) return res.status(404).json({ error: 'Projet non trouve', code: 'NOT_FOUND' });

    const projectTrackers = trackers.filter(t => t._projectId === oid.toString()).map(t => ({
      _id: t._id,
      name: t.name,
      _isConnected: t._isConnected,
      _batteryVolt: t._batteryVolt,
      _batteryStatus: t._batteryStatus,
      _lastSeenSeconds: t._lastSeenSeconds,
      _healthScore: t._healthScore,
    }));

    res.json({
      ...enrichProject(project, trackers),
      trackers: projectTrackers,
    });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
