'use strict';
const { test } = require('node:test');
const assert   = require('node:assert/strict');
const { computeWorstProjects, computeFleetHealthScore } = require('./fleet');

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeTracker(pid, { connected = true, battOk = true, weight = null } = {}) {
  const lastUpdate = connected
    ? new Date(Date.now() - 5_000).toISOString()
    : new Date(Date.now() - 7_200_000).toISOString(); // 2h ago
  const battery_volt = battOk ? 4.0 : 3.0;
  const msg = { battery_volt, ...(weight !== null ? { weight } : {}) };
  return { _projectId: pid, lastUpdate, lastTrack: { message: msg } };
}

function makeProject(id, name, offlineDelay = 60) {
  return { id, name, offlineDelay };
}

// ── computeWorstProjects ──────────────────────────────────────────────────────

test('retourne [] si aucun projet actif', () => {
  assert.deepEqual(computeWorstProjects([], []), []);
});

test('exclut les projets sans capteurs', () => {
  const p = makeProject('p1', 'Proj A');
  const result = computeWorstProjects([p], []);
  assert.equal(result.length, 0);
});

test('retourne le projet avec son score', () => {
  const p = makeProject('p1', 'Proj A');
  const t = makeTracker('p1', { connected: true, battOk: true });
  const result = computeWorstProjects([p], [t]);
  assert.equal(result.length, 1);
  assert.equal(result[0].name, 'Proj A');
  assert.equal(result[0].score, 80); // connexion 50 + batterie 30, peson absent
});

test('trie par score croissant (le plus dégradé en premier)', () => {
  const pA = makeProject('pA', 'Bon projet');
  const pB = makeProject('pB', 'Mauvais projet');
  const tA = makeTracker('pA', { connected: true,  battOk: true  }); // score 80
  const tB = makeTracker('pB', { connected: false, battOk: false }); // score 0
  const result = computeWorstProjects([pA, pB], [tA, tB]);
  assert.equal(result[0].name, 'Mauvais projet');
  assert.equal(result[1].name, 'Bon projet');
});

test('limite à N projets (défaut 3)', () => {
  const projects = ['A','B','C','D'].map(id => makeProject(id, `Proj ${id}`));
  const trackers  = ['A','B','C','D'].map(id => makeTracker(id, { connected: false }));
  const result = computeWorstProjects(projects, trackers);
  assert.equal(result.length, 3);
});

test('respecte le paramètre n', () => {
  const projects = ['A','B'].map(id => makeProject(id, `Proj ${id}`));
  const trackers  = ['A','B'].map(id => makeTracker(id));
  assert.equal(computeWorstProjects(projects, trackers, 1).length, 1);
});

test('score 100 si connecté + batterie ok + peson présent', () => {
  const p = makeProject('p1', 'Top');
  const t = makeTracker('p1', { connected: true, battOk: true, weight: 1200 });
  const result = computeWorstProjects([p], [t]);
  assert.equal(result[0].score, 100);
});

test('utilise offlineDelay du projet pour la connexion', () => {
  const p = makeProject('p1', 'Lent', 7200); // délai 2h
  // lastUpdate il y a 1h : connecté avec délai 2h, déconnecté avec délai 60s
  const lastUpdate = new Date(Date.now() - 3_600_000).toISOString();
  const t = { _projectId: 'p1', lastUpdate, lastTrack: { message: { battery_volt: 4.0 } } };
  const result = computeWorstProjects([p], [t]);
  // avec offlineDelay=7200 → connecté → score 80
  assert.equal(result[0].score, 80);
});

// ── computeFleetHealthScore ──────────────────────────────────────────────────

test('retourne null si aucun projet actif', () => {
  assert.equal(computeFleetHealthScore([], []), null);
});

test('retourne null si tous les projets actifs sont sans capteurs', () => {
  const p = makeProject('p1', 'Vide');
  assert.equal(computeFleetHealthScore([p], []), null);
});

test('retourne le score moyen de deux projets', () => {
  const pA = makeProject('pA', 'A');
  const pB = makeProject('pB', 'B');
  const tA = makeTracker('pA', { connected: true,  battOk: true  }); // 80
  const tB = makeTracker('pB', { connected: false, battOk: false }); // 0
  const score = computeFleetHealthScore([pA, pB], [tA, tB]);
  assert.equal(score, 40); // (80+0)/2
});

test('ignore les projets sans capteurs dans la moyenne', () => {
  const pA = makeProject('pA', 'Avec capteurs');
  const pB = makeProject('pB', 'Sans capteurs');
  const tA = makeTracker('pA', { connected: true, battOk: true }); // 80
  const score = computeFleetHealthScore([pA, pB], [tA]);
  assert.equal(score, 80); // seul pA compte
});
