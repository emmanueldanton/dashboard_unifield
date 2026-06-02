'use strict';

// Métriques agrégées au niveau flotte — fonctions pures, testables sans Express.

const { healthScore } = require('./trackers');

/**
 * Retourne les N projets avec le score santé le plus bas.
 *
 * @param {object[]} projects    - projets non archivés récemment actifs (fenêtre 30j)
 *                                 Ne pas passer segs.active (60s) : trop restrictif.
 * @param {object[]} allTrackers - tous les trackers enrichis du cache
 * @param {number}   n           - nombre de projets à retourner (défaut 3)
 * @returns {{ id, name, score, trackerCount }[]}  triés score croissant
 */
function computeWorstProjects(activeProjects, allTrackers, n = 3) {
  return activeProjects
    .map(p => {
      const pid = (p.id || p._id || '').toString();
      const pTrackers = allTrackers.filter(
        t => (t._projectId || t._project_id || '') === pid
      );
      const offlineDelay = p.offlineDelay || 60;
      // Dernière activité = lastUpdate le plus récent parmi les trackers du projet
      let lastActivity = null;
      for (const t of pTrackers) {
        if (t.lastUpdate && (!lastActivity || t.lastUpdate > lastActivity)) {
          lastActivity = t.lastUpdate;
        }
      }
      return {
        id:           pid,
        name:         p.name || pid,
        score:        healthScore(pTrackers, offlineDelay),
        trackerCount: pTrackers.length,
        lastActivity,
      };
    })
    .filter(p => p.trackerCount > 0)
    .sort((a, b) => a.score - b.score)
    .slice(0, n);
}

/**
 * Score santé global de la flotte = moyenne des scores des projets actifs.
 * Retourne null si aucun projet actif avec capteurs.
 *
 * @param {object[]} activeProjects
 * @param {object[]} allTrackers
 * @returns {number|null}
 */
function computeFleetHealthScore(activeProjects, allTrackers) {
  const scores = activeProjects
    .map(p => {
      const pid = (p.id || p._id || '').toString();
      const pTrackers = allTrackers.filter(
        t => (t._projectId || t._project_id || '') === pid
      );
      if (!pTrackers.length) return null;
      return healthScore(pTrackers, p.offlineDelay || 60);
    })
    .filter(s => s !== null);
  if (!scores.length) return null;
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
}

module.exports = { computeWorstProjects, computeFleetHealthScore };
