'use strict';
const { Router } = require('express');
const { getData } = require('../db/cache');
const { healthScore } = require('../lib/trackers');
const { projectStatus } = require('../lib/segments');
const { ObjectId } = require('mongodb');

const router = Router();

function enrichProject(project, allTrackers) {
  // Le loader retourne project.id (string dbname) - pas project._id
  const pid = (project.id || project._id || '').toString();
  const projectTrackers = allTrackers.filter(t =>
    t._projectId === pid || t._project_id === pid
  );
  return {
    _id: pid,
    name: project.name,
    code: project.code || '',
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
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    const { projects, trackers } = cached;
    const enriched = projects.map(p => enrichProject(p, trackers));
    res.json({ projects: enriched });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

router.get('/:id', async (req, res) => {
  const reqId = req.params.id;

  try {
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    const { projects, trackers } = cached;
    const project = projects.find(p =>
      (p.id || p._id || '').toString() === reqId
    );
    if (!project) return res.status(404).json({ error: 'Projet non trouve', code: 'NOT_FOUND' });

    const pid = (project.id || project._id || '').toString();
    const projectTrackers = trackers.filter(t =>
      t._projectId === pid || t._project_id === pid
    ).map(t => ({
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
