'use strict';

// Port de api/mongo_loader.py - architecture registre central + bases per-projet

const REGISTRY_DB  = 'cad42Users';
const REGISTRY_COL = 'projects';
const ACTIVE_TRACKER_SECONDS = 30;
const DEFAULT_OFFLINE_DELAY  = 3600;
const MAX_P1_WORKERS = 4;

function dtToIso(v) {
  if (!v) return null;
  if (v instanceof Date) return v.toISOString();
  return String(v);
}

function oidToStr(v) {
  return v != null ? String(v) : '';
}

function adaptTracker(raw, resolvedLastTrack) {
  const t = { ...raw };
  t._id       = oidToStr(t._id);
  t.uuid      = t.uuid || t._id;
  t.lastUpdate = dtToIso(t.lastUpdate);

  const lt  = resolvedLastTrack || {};
  const msg = (lt.message && typeof lt.message === 'object') ? { ...lt.message } : {};

  // Fallback batteryLevel (%) -> battery_volt si absent
  if (!('battery_volt' in msg)) {
    const pct = t.batteryLevel;
    if (typeof pct === 'number' && pct >= 0) {
      msg.battery_volt = parseFloat((3.0 + (pct / 100) * 1.2).toFixed(2));
    }
  }

  t.lastTrack = { ...lt, message: msg };

  for (const field of ['project', 'config']) {
    if (field in t && typeof t[field] !== 'string') t[field] = oidToStr(t[field]);
  }
  return t;
}

function hasActiveTracker(trackers, now) {
  for (const t of trackers) {
    if (!t.lastUpdate) continue;
    try {
      const dt = new Date(t.lastUpdate);
      if ((now - dt) / 1000 <= ACTIVE_TRACKER_SECONDS) return true;
    } catch { /* skip */ }
  }
  return false;
}

function lastSeenSeconds(t) {
  if (!t.lastUpdate) return -1;
  return Math.floor((Date.now() - new Date(t.lastUpdate)) / 1000);
}

function isConnected(t, offlineDelay) {
  const s = lastSeenSeconds(t);
  return s >= 0 && s < offlineDelay;
}

function batteryVolt(t) {
  const v = t.lastTrack?.message?.battery_volt ?? t._battery_volt ?? -1;
  const n = parseFloat(v);
  return isNaN(n) ? -1 : n;
}

function batteryStatus(t, threshold = 3.5) {
  const v = batteryVolt(t);
  if (v < 0) return 'inconnu';
  return v < threshold ? 'faible' : 'ok';
}

// Charge le registre central cad42Users.projects
async function loadRegistry(client) {
  try {
    const db   = client.db(REGISTRY_DB);
    const docs = await db.collection(REGISTRY_COL).find(
      { database: { $exists: true, $ne: '' } },
      { projection: { name: 1, code: 1, type: 1, description: 1, startDate: 1,
                      endDate: 1, archived: 1, offlineDelay: 1, city: 1,
                      schedule: 1, database: 1, timezone: 1 } }
    ).toArray();

    const registry = {};
    for (const doc of docs) {
      if (doc.database) registry[doc.database] = doc;
    }
    return registry;
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'registry_load_failed', detail: err.message }));
    return {};
  }
}

// Phase 1 : trackers d'une base projet
async function phase1LoadTrackers(client, dbname, now, projectDoc) {
  const db = client.db(dbname);

  let cols;
  try {
    cols = new Set(await db.listCollections().toArray().then(c => c.map(x => x.name)));
  } catch { return null; }

  if (!cols.has('trackers')) return null;

  let rawTrackers;
  try {
    rawTrackers = await db.collection('trackers').find({}, {
      projection: { uuid: 1, name: 1, type: 1, version: 1, lastTrack: 1,
                    lastUpdate: 1, batteryLevel: 1, project: 1, description: 1 }
    }).toArray();
  } catch { return null; }

  if (!rawTrackers.length) return null;

  const reg         = projectDoc || {};
  const parts       = dbname.split('_');
  const fallbackName = parts.length > 1 ? parts.slice(1).join('_') : dbname;
  const fallbackCode = parts[0];

  const pid          = dbname;
  const name         = reg.name || fallbackName;
  const offlineDelay = parseInt(reg.offlineDelay || DEFAULT_OFFLINE_DELAY, 10);

  const projectMeta = {
    id:           pid,
    name,
    code:         reg.code || fallbackCode,
    archived:     Boolean(reg.archived),
    offlineDelay,
    startDate:    dtToIso(reg.startDate),
    endDate:      dtToIso(reg.endDate),
    type:         reg.type || 'construction',
    city:         reg.city || '',
    schedule:     reg.schedule || {},
    timezone:     reg.timezone || 'UTC',
    database:     dbname,
  };

  // Résolution batch lastTrack ObjectId -> document tracks
  const lastTrackOids = rawTrackers
    .filter(t => t.lastTrack && typeof t.lastTrack === 'object' && t.lastTrack._bsontype)
    .map(t => t.lastTrack);

  const tracksById = {};
  if (lastTrackOids.length && cols.has('tracks')) {
    try {
      const trkDocs = await db.collection('tracks').find(
        { _id: { $in: lastTrackOids } }
      ).toArray();
      for (const tr of trkDocs) tracksById[String(tr._id)] = tr;
    } catch { /* best-effort */ }
  }

  const trackerMap = {};
  for (const rawT of rawTrackers) {
    const ltRef = rawT.lastTrack;
    let resolved = null;
    if (ltRef && typeof ltRef === 'object' && ltRef._bsontype) {
      resolved = tracksById[String(ltRef)] || null;
    } else if (ltRef && typeof ltRef === 'object') {
      resolved = ltRef;
    }

    const t = adaptTracker(rawT, resolved);
    t._project_id        = pid;
    t._project_name      = name;
    t._offline_delay     = offlineDelay;
    t._unit_id           = '';
    t._unit_name         = '-';
    t._is_connected      = isConnected(t, offlineDelay);
    t._battery_status    = batteryStatus(t);
    t._battery_volt      = batteryVolt(t);
    t._last_seen_seconds = lastSeenSeconds(t);
    const _w             = t.lastTrack?.message?.weight;
    t._weight_status     = (_w === undefined || _w === null || _w < 0) ? 'inconnu' : 'ok';

    // Enrichissements Sentinel (camelCase pour l'API)
    t._isConnected      = t._is_connected;
    t._batteryStatus    = t._battery_status;
    t._batteryVolt      = t._battery_volt;
    t._lastSeenSeconds  = t._last_seen_seconds;
    t._projectId        = pid;
    t._projectName      = name;
    t._healthScore      = computeTrackerHealth(t);

    const oidStr = oidToStr(rawT._id);
    if (oidStr) trackerMap[oidStr] = t;
  }

  const isActive = hasActiveTracker(Object.values(trackerMap), now);
  return { projectMeta, trackerMap, isActive };
}

function computeTrackerHealth(t) {
  // Iso-Python (business/trackers.py health_score) : 50 connexion + 30 batterie + 20 peson.
  const conn  = t._is_connected ? 50 : 0;
  const batt  = t._battery_status === 'ok' ? 30 : 0;
  const w     = t.lastTrack?.message?.weight;
  const peson = (w !== undefined && w !== null && w >= 0) ? 20 : 0;
  return conn + batt + peson;
}

// Phase 2 : units + events pour une base active
async function phase2LoadDetails(client, dbname, pid, name, trackerMap, offlineDelay) {
  const db = client.db(dbname);
  let cols;
  try {
    cols = new Set(await db.listCollections().toArray().then(c => c.map(x => x.name)));
  } catch { cols = new Set(); }

  let units = [];
  if (cols.has('units')) {
    try {
      const raw = await db.collection('units').find({}, {
        projection: { name: 1, type: 1, trackers: 1, startDate: 1, lastUpdate: 1, status: 1 }
      }).toArray();
      units = raw.map(u => ({
        ...u,
        _id:          oidToStr(u._id),
        trackers:     (u.trackers || []).map(String),
        _project_id:  pid,
        _project_name: name,
      }));
    } catch { /* skip */ }
  }

  let events = [];
  if (cols.has('events')) {
    try {
      const raw = await db.collection('events').find({}, { limit: 50 }).toArray();
      events = raw.map(e => ({ ...e, _id: oidToStr(e._id), _project_id: pid }));
    } catch { /* skip */ }
  }

  // Association trackers -> units
  for (const u of units) {
    for (const ref of (u.trackers || [])) {
      const t = trackerMap[ref];
      if (t) { t._unit_id = u._id; t._unit_name = u.name || '-'; }
    }
  }

  return { units, trackers: Object.values(trackerMap), events };
}

async function loadAllData() {
  const { getClient } = require('./mongo');
  const client = await getClient();
  const now    = new Date();

  // Pre-phase : registre central
  const registry    = await loadRegistry(client);
  let projectDbs    = Object.keys(registry);

  // Fallback si registre inaccessible
  if (!projectDbs.length) {
    console.warn(JSON.stringify({ ts: now.toISOString(), event: 'registry_fallback' }));
    try {
      const allDbs = await client.db().admin().listDatabases();
      projectDbs = allDbs.databases
        .map(d => d.name)
        .filter(n => /^\d+_/.test(n));
    } catch { return { projects: [], trackers: [], project_data: {}, loaded_at: now }; }
  }

  // Phase 1 : trackers de toutes les bases (parallele, MAX_P1_WORKERS)
  const p1Results = {};
  const chunks = [];
  for (let i = 0; i < projectDbs.length; i += MAX_P1_WORKERS) {
    chunks.push(projectDbs.slice(i, i + MAX_P1_WORKERS));
  }

  for (const chunk of chunks) {
    const results = await Promise.all(
      chunk.map(dbname => phase1LoadTrackers(client, dbname, now, registry[dbname])
        .catch(() => null))
    );
    chunk.forEach((dbname, i) => { p1Results[dbname] = results[i]; });
  }

  const phase1 = projectDbs
    .filter(db => p1Results[db] != null)
    .map(db => p1Results[db]);

  // Phase 2 : detail des bases actives uniquement
  const projects     = [];
  const project_data = {};
  let   allTrackers  = [];

  for (const { projectMeta, trackerMap, isActive } of phase1) {
    projects.push({ ...projectMeta, active: isActive });

    if (!isActive) {
      allTrackers = allTrackers.concat(Object.values(trackerMap));
      continue;
    }

    try {
      const pdata = await phase2LoadDetails(
        client, projectMeta.id, projectMeta.id, projectMeta.name,
        trackerMap, projectMeta.offlineDelay
      );
      pdata.timezone = projectMeta.timezone;
      project_data[projectMeta.id] = pdata;
      allTrackers = allTrackers.concat(pdata.trackers);
    } catch {
      allTrackers = allTrackers.concat(Object.values(trackerMap));
    }
  }

  return { projects, trackers: allTrackers, project_data, loaded_at: now };
}

module.exports = { loadAllData };
