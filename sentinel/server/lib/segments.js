'use strict';

// Port exact de business/segments.py
//
// NOTE architecture cache : _last_seen_seconds est calculé au chargement du cache
// (loader.js), en même temps que le snapshot MongoDB. On utilise CETTE valeur figée
// et non un recalcul frais : le snapshot lui-même fige lastUpdate, donc comparer
// Date.now() à un lastUpdate figé donnerait des valeurs erronées (→ 0 projet actif).

const ENDING_SOON_DAYS = 7;

function isArchived(project) {
  return project.archived === true;
}

function isActive(project) {
  if (isArchived(project)) return false;
  if (!project.endDate) return true;
  return new Date(project.endDate) > Date.now();
}

function isEnding(project, endingDays = ENDING_SOON_DAYS) {
  if (!isActive(project)) return false;
  if (!project.endDate) return false;
  const msToEnd = new Date(project.endDate) - Date.now();
  const daysToEnd = msToEnd / 86400000;
  return daysToEnd > 0 && daysToEnd <= endingDays;
}

function projectStatus(project) {
  if (isArchived(project)) return 'archive';
  if (!isActive(project)) return 'termine';
  if (isEnding(project)) return 'se_terminant';
  return 'actif';
}

// Port exact de business/segments.py -> compute_segments()
// Classe les projets en buckets {archived, past, total, active, ending, anomalies}.
function computeSegments(projects, projectData, now, activitySec, endingDays, pastDays) {
  const nowMs = now instanceof Date ? now.getTime() : new Date(now).getTime();

  const hasSignalToday = (p) => {
    const trkrs = (projectData[p.id || ''] || {}).trackers || [];
    return trkrs.some(t => {
      const s = t._last_seen_seconds ?? t._lastSeenSeconds ?? -1;
      return s >= 0 && s < activitySec;
    });
  };

  const archived = [], past = [], total = [], active = [], ending = [], anomalies = [];

  for (const p of projects) {
    const end   = p.endDate;
    const isArch = p.archived === true;
    let endDiff = null;

    if (end) {
      const endMs = new Date(end).getTime();
      if (!Number.isNaN(endMs)) endDiff = Math.floor((nowMs - endMs) / 86400000);
    }

    if (isArch) { archived.push(p); continue; }

    const signal = hasSignalToday(p);

    if (endDiff !== null && endDiff > 0) {
      past.push(p);
      if (signal) { active.push(p); anomalies.push(p); }
      continue;
    }

    total.push(p);
    if (signal) active.push(p);

    if (end) {
      const endMs = new Date(end).getTime();
      if (!Number.isNaN(endMs)) {
        const diffFuture = Math.floor((endMs - nowMs) / 86400000);
        if (diffFuture > 0 && diffFuture < Number(endingDays)) ending.push(p);
      }
    }
  }

  return { archived, past, total, active, ending, anomalies };
}

module.exports = { isActive, isEnding, isArchived, projectStatus, computeSegments };
