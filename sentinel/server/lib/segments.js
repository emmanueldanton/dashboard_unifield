'use strict';

// Port exact de business/segments.py

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
  // Le loader marque project.active = false si aucun tracker recent (30s)
  // On garde le critere endDate comme critere "termine"
  if (!isActive(project)) return 'termine';
  if (isEnding(project)) return 'se_terminant';
  return 'actif';
}

// Port exact de business/segments.py -> compute_segments()
// Classe les projets en buckets {archived, past, total, active, ending, anomalies}.
// - active   : >=1 tracker vu il y a moins de `activitySec` secondes (signal)
// - ending   : endDate dans le futur, strictement 0 < jours < endingDays
// - past     : endDate depassee (endDiff > 0), non archive
// - anomalies: projet "past" mais qui emet encore un signal (termine + actif)
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
    const end = p.endDate;
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
