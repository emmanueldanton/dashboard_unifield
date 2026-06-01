'use strict';
const { enrichTracker } = require('../lib/trackers');

async function loadAllData(db) {
  // Phase 1: lightweight load of all projects and trackers
  const [projects, trackers] = await Promise.all([
    db.collection('projects').find({}, {
      projection: { name: 1, code: 1, archived: 1, endDate: 1, startDate: 1 },
    }).toArray(),
    db.collection('trackers').find({}, {
      projection: { name: 1, project: 1, lastUpdate: 1, 'lastTrack.message': 1 },
    }).toArray(),
  ]);

  // Association tracker -> project in memory (no $lookup)
  const projectMap = new Map(projects.map(p => [p._id.toString(), p]));
  for (const t of trackers) {
    const proj = projectMap.get(t.project?.toString());
    t._projectId = proj?._id?.toString() ?? null;
    t._projectName = proj?.name ?? null;
    enrichTracker(t);
  }

  // Phase 2: detail for active projects only
  const now = Date.now();
  const activeProjectIds = projects
    .filter(p => !p.archived && (!p.endDate || new Date(p.endDate) > now))
    .map(p => p._id);

  const project_data = {};
  if (activeProjectIds.length > 0) {
    const [units, events] = await Promise.all([
      db.collection('units').find(
        { project: { $in: activeProjectIds } },
        { projection: { name: 1, project: 1 } }
      ).toArray(),
      db.collection('events').find(
        { project: { $in: activeProjectIds } },
        { projection: { project: 1, tracker: 1, ts: 1, type: 1 } }
      ).toArray(),
    ]);

    for (const id of activeProjectIds) {
      const key = id.toString();
      project_data[key] = {
        units: units.filter(u => u.project.toString() === key),
        events: events.filter(e => e.project.toString() === key),
      };
    }
  }

  return { projects, trackers, project_data, loaded_at: new Date() };
}

module.exports = { loadAllData };
