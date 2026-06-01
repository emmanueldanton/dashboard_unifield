'use strict';
const { Router } = require('express');
const { getData } = require('../db/cache');
const { filterData } = require('../lib/flags');

const router = Router();

// Projette un tracker enrichi (loader) vers la forme attendue par le frontend.
// Champs alignes sur build_tracker_rows / show_modal_capteur (Python Dash).
function mapTracker(t) {
  const lt = t.lastTrack || {};
  const msg = (lt.message && typeof lt.message === 'object') ? lt.message : {};
  const num = v => (typeof v === 'number' && !Number.isNaN(v) ? v : null);
  return {
    _id:             t._id,
    uuid:            t.uuid,
    name:            t.name,
    _projectId:      t._projectId || t._project_id || '',
    _projectName:    t._projectName || t._project_name || '',
    _unitName:       t._unit_name || '-',
    _projectTz:      t._project_tz || 'UTC',
    _isConnected:    !!t._isConnected,
    _batteryVolt:    t._batteryVolt,
    _batteryStatus:  t._batteryStatus,
    _lastSeenSeconds: t._lastSeenSeconds,
    _healthScore:    t._healthScore,
    lastUpdate:      t.lastUpdate || null,
    // Mesures du dernier message
    shackleBattery:  num(msg.shackle_battery),
    temperature:     num(msg.temperature),
    weight:          num(msg.weight),
    lat:             num(lt.lat),
    lon:             num(lt.lon),
  };
}

// GET /api/trackers
//   ?all=1                -> renvoie tout le parc (filtre parasites/has_data) pour
//                            un traitement instantane cote client (tri/filtre/recherche)
//   sinon                 -> pagination + filtres serveur (compat ascendante)
router.get('/', async (req, res) => {
  try {
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    const { trackers } = filterData(cached);

    if (req.query.all === '1' || req.query.all === 'true') {
      const all = trackers.map(mapTracker);
      return res.json({ trackers: all, total: all.length });
    }

    const page = Math.max(1, parseInt(req.query.page || '1', 10));
    const limit = Math.min(50, Math.max(1, parseInt(req.query.limit || '50', 10)));

    let filtered = trackers;
    if (req.query.connected !== undefined) {
      const want = req.query.connected === 'true';
      filtered = filtered.filter(t => t._isConnected === want);
    }
    if (req.query.battery) {
      filtered = filtered.filter(t => t._batteryStatus === req.query.battery);
    }
    if (req.query.project) {
      filtered = filtered.filter(t => (t._projectId || t._project_id) === req.query.project);
    }

    filtered = filtered.slice().sort((a, b) => b._healthScore - a._healthScore);

    const total = filtered.length;
    const start = (page - 1) * limit;
    const page_items = filtered.slice(start, start + limit).map(mapTracker);

    res.json({ trackers: page_items, total, page, limit });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'api_error', path: '/api/trackers', detail: err.message }));
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

const BOOT_KEYWORDS = ['boot', 'start', 'connect', 'online', 'power', 'init',
  'wake', 'restart', 'reboot', 'activate'];

function parisDateKey(d) {
  // "YYYY-MM-DD" dans le fuseau Europe/Paris
  try {
    return new Intl.DateTimeFormat('fr-CA', {
      timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(d);
  } catch { return ''; }
}

// GET /api/trackers/:id  -> detail events d'un capteur (port de show_modal_capteur)
router.get('/:id', async (req, res) => {
  const reqId = req.params.id;
  try {
    const cached = await getData();
    if (!cached) return res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
    const { trackers, project_data } = filterData(cached);
    const tracker = trackers.find(t => t._id === reqId || t.uuid === reqId);
    if (!tracker) return res.status(404).json({ error: 'Capteur non trouve', code: 'NOT_FOUND' });

    const pid = tracker._projectId || tracker._project_id || '';
    const allEvents = (project_data[pid] || {}).events || [];

    const matchesTracker = (e) => {
      const refs = e.trackers || [];
      if (!refs.length) return true; // event projet-wide
      return refs.some(r => (typeof r === 'string' ? r : (r && r.id) || '') === reqId);
    };

    const todayParis = parisDateKey(new Date());
    let bootThisMorning = null;

    const events = allEvents
      .filter(matchesTracker)
      .map(e => ({
        ts:      e.timestamp || e.createdAt || e.date || '',
        type:    e.type || e.eventType || '?',
        message: String(e.message || e.msg || e.data || '').slice(0, 120),
      }));

    for (const e of events) {
      const blob = `${e.type} ${e.message}`.toLowerCase();
      if (e.ts && BOOT_KEYWORDS.some(kw => blob.includes(kw))) {
        const dt = new Date(String(e.ts).replace('Z', '+00:00'));
        if (!Number.isNaN(dt.getTime()) && parisDateKey(dt) === todayParis) {
          if (bootThisMorning === null || dt < new Date(bootThisMorning)) {
            bootThisMorning = dt.toISOString();
          }
        }
      }
    }

    events.sort((a, b) => String(b.ts).localeCompare(String(a.ts)));

    res.json({
      tracker: mapTracker(tracker),
      events: events.slice(0, 10),
      eventsTotal: events.length,
      bootThisMorning,
    });
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'api_error', path: '/api/trackers/:id', detail: err.message }));
    res.status(503).json({ error: 'Service indisponible', code: 'SERVICE_UNAVAILABLE' });
  }
});

module.exports = router;
