'use strict';
const { Router } = require('express');
const { getData } = require('../db/cache');
const { healthScore } = require('../lib/trackers');
const { isArchived } = require('../lib/segments');
const { filterData } = require('../lib/flags');

const router = Router();

const ACTIVITY_WINDOW_SECONDS = 60;
const ENDING_SOON_DAYS = 30; // aligné avec kpis.js (cohérence KPI ↔ filtre)

// Signal "actif" = au moins 1 capteur vu il y a moins de 60s.
// Utilise la valeur figée _last_seen_seconds du cache (cohérent avec segments.js et
// l'architecture cache : recalculer frais contre un snapshot figé donne 0 actif).
function hasActiveSignal(projectTrackers) {
  return projectTrackers.some(t => {
    const s = t._last_seen_seconds ?? t._lastSeenSeconds ?? -1;
    return s >= 0 && s < ACTIVITY_WINDOW_SECONDS;
  });
}

// Flags de cycle de vie indépendants du statut d'activité.
// Un projet peut être "actif" (signal récent) ET en fin imminente ET/OU terminé sur papier.
function lifecycleFlags(project) {
  const now   = Date.now();
  const endMs = project.endDate ? new Date(project.endDate).getTime() : NaN;
  if (Number.isNaN(endMs)) return { ended: false, endingSoon: false };
  const past       = endMs < now;
  const daysToEnd  = (endMs - now) / 86400000;
  return {
    ended:      past,
    endingSoon: daysToEnd > 0 && daysToEnd < ENDING_SOON_DAYS,
  };
}

// Statut PRIMAIRE d'un projet = état d'activité.
// Le signal prime : un projet avec capteur actif est "actif", quel que soit son cycle de vie.
// Les états fin imminente / terminé sont portés par les flags (mentions affichées en plus).
function computeProjectStatus(project, projectTrackers) {
  if (isArchived(project)) return 'archive';

  if (hasActiveSignal(projectTrackers)) return 'actif';

  const { ended, endingSoon } = lifecycleFlags(project);
  if (ended)      return 'termine';
  if (endingSoon) return 'se_terminant';

  return 'inactif';
}

function enrichProject(project, allTrackers, projectData) {
  const pid = (project.id || project._id || '').toString();
  const projectTrackers = allTrackers.filter(t =>
    t._projectId === pid || t._project_id === pid
  );

  const offlineDelay   = project.offlineDelay || 60;
  const connectedCount = projectTrackers.filter(t => t._isConnected || t._is_connected).length;
  const batteryLowCount = projectTrackers.filter(t =>
    (t._batteryStatus || t._battery_status) === 'faible'
  ).length;

  let lastActivity = null;
  for (const t of projectTrackers) {
    const lu = t.lastUpdate;
    if (lu && (!lastActivity || lu > lastActivity)) lastActivity = lu;
  }

  const timezone = project.timezone
    || (projectData && projectData[pid] && projectData[pid].timezone)
    || 'UTC';

  const { ended, endingSoon } = lifecycleFlags(project);

  return {
    _id: pid,
    name: project.name,
    code: project.code || '',
    type: project.type || '',
    startDate: project.startDate || null,
    endDate: project.endDate || null,
    archived: project.archived || false,
    _status: computeProjectStatus(project, projectTrackers),
    // Flags de cycle de vie bruts — le frontend affiche les mentions et filtre dessus
    _ended:      ended,       // endDate dépassée
    _endingSoon: endingSoon,  // fin dans moins de 30 jours
    _trackerCount: projectTrackers.length,
    _connectedCount: connectedCount,
    _batteryLowCount: batteryLowCount,
    _healthScore: healthScore(projectTrackers, offlineDelay),
    _lastActivity: lastActivity,
    _timezone: timezone,
  };
}

router.get('/', async (_req, res) => {
  try {
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    // filterData : retire les projets parasites (atelier/stock/test/dev) + trackers sans données
    const { projects, trackers, project_data } = filterData(cached);
    const filtered = projects.filter(p => p.type !== 'KYD');
    const enriched = filtered.map(p => enrichProject(p, trackers, project_data || {}));
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
    // filterData : retire les projets parasites (atelier/stock/test/dev) + trackers sans données
    const { projects, trackers, project_data } = filterData(cached);
    const project = projects.find(p => (p.id || p._id || '').toString() === reqId);
    if (!project) return res.status(404).json({ error: 'Projet non trouve', code: 'NOT_FOUND' });

    const pid = (project.id || project._id || '').toString();
    const offlineDelay = project.offlineDelay || 60;
    const projectTrackers = trackers.filter(t =>
      t._projectId === pid || t._project_id === pid
    ).map(t => ({
      _id: t._id,
      name: t.name,
      _isConnected: t._isConnected ?? t._is_connected ?? false,
      _batteryVolt: t._batteryVolt ?? t._battery_volt ?? -1,
      _batteryStatus: t._batteryStatus || t._battery_status || 'inconnu',
      _lastSeenSeconds: t._lastSeenSeconds ?? t._last_seen_seconds ?? -1,
      _healthScore: t._healthScore ?? 0,
      _unitName: t._unitName || t._unit_name || '-',
    }));

    res.json({
      ...enrichProject(project, trackers, project_data || {}),
      offlineDelay,
      trackers: projectTrackers,
    });
  } catch (err) {
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
