'use strict';

// Port exact de business/flags.py -> filter_data()
// Exclut les projets parasites (atelier/stock/test/dev) et ne conserve que
// les trackers porteurs de donnees (lastTrack.message non vide).

const PARASITE_KEYWORDS = ['atelier', 'stock', 'test', 'dev'];

function hasData(t) {
  const lt = t.lastTrack || {};
  const msg = lt.message;
  // Python : bool(lt.get("message")) -> un dict vide est falsy.
  return !!msg && typeof msg === 'object' && Object.keys(msg).length > 0;
}

function filterData(data) {
  const projects = data.projects || [];
  const trackers = data.trackers || [];
  const projectData = data.project_data || {};

  const bad = new Set(
    projects
      .filter(p => {
        const name = (p.name || '').toLowerCase();
        return PARASITE_KEYWORDS.some(kw => name.includes(kw));
      })
      .map(p => p.id)
  );

  const filteredProjectData = {};
  for (const [pid, pinfo] of Object.entries(projectData)) {
    if (bad.has(pid)) continue;
    filteredProjectData[pid] = {
      ...pinfo,
      trackers: (pinfo.trackers || []).filter(hasData),
    };
  }

  return {
    ...data,
    projects: projects.filter(p => !bad.has(p.id)),
    trackers: trackers.filter(t => !bad.has(t._project_id) && hasData(t)),
    project_data: filteredProjectData,
  };
}

module.exports = { filterData, hasData, PARASITE_KEYWORDS };
