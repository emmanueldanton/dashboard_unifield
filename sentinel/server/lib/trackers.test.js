'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const {
  isConnected, batteryVolt, batteryStatus, weightStatus,
  lastSeenSeconds, healthScore, isOperational, STALE_TRACKER_DAYS,
} = require('./trackers');

// ── Helpers ──────────────────────────────────────────────────────────────────

function recent(offsetSecs = 5) {
  return new Date(Date.now() - offsetSecs * 1000).toISOString();
}
function daysAgo(n) {
  return new Date(Date.now() - n * 86400 * 1000).toISOString();
}

// ── isConnected ──────────────────────────────────────────────────────────────

test('isConnected retourne false si lastUpdate est null', () => {
  assert.equal(isConnected({ lastUpdate: null }), false);
});

test('isConnected retourne false si lastUpdate est undefined', () => {
  assert.equal(isConnected({}), false);
});

test('isConnected retourne true si lastUpdate recente (< 60s)', () => {
  assert.equal(isConnected({ lastUpdate: recent(10) }), true);
});

test('isConnected retourne false si lastUpdate ancienne (> 60s)', () => {
  assert.equal(isConnected({ lastUpdate: recent(120) }), false);
});

// ── batteryVolt / batteryStatus ───────────────────────────────────────────────

test('batteryVolt extrait depuis lastTrack.message.battery_volt', () => {
  assert.equal(batteryVolt({ lastTrack: { message: { battery_volt: 3.8 } } }), 3.8);
});

test('batteryVolt retourne -1 si absent', () => {
  assert.equal(batteryVolt({}), -1);
  assert.equal(batteryVolt({ lastTrack: {} }), -1);
  assert.equal(batteryVolt({ lastTrack: { message: {} } }), -1);
});

test('batteryStatus retourne "faible" en dessous de 3.5V', () => {
  assert.equal(batteryStatus({ lastTrack: { message: { battery_volt: 3.2 } } }), 'faible');
});

test('batteryStatus retourne "ok" a 3.5V et au dessus', () => {
  assert.equal(batteryStatus({ lastTrack: { message: { battery_volt: 3.7 } } }), 'ok');
});

test('batteryStatus retourne "inconnu" si battery_volt absent', () => {
  assert.equal(batteryStatus({}), 'inconnu');
});

// ── weightStatus ─────────────────────────────────────────────────────────────

test('weightStatus retourne "ok" si weight present et >= 0', () => {
  assert.equal(weightStatus({ lastTrack: { message: { weight: 1200 } } }), 'ok');
  assert.equal(weightStatus({ lastTrack: { message: { weight: 0 } } }), 'ok');
});

test('weightStatus retourne "inconnu" si weight absent ou negatif', () => {
  assert.equal(weightStatus({}), 'inconnu');
  assert.equal(weightStatus({ lastTrack: { message: {} } }), 'inconnu');
  assert.equal(weightStatus({ lastTrack: { message: { weight: -1 } } }), 'inconnu');
});

// ── isOperational ─────────────────────────────────────────────────────────────

test('isOperational retourne false si lastUpdate est null (jamais deploye)', () => {
  assert.equal(isOperational({ lastUpdate: null }), false);
  assert.equal(isOperational({}), false);
});

test('isOperational retourne true si vu recemment', () => {
  assert.equal(isOperational({ lastUpdate: recent(30) }), true);
});

test(`isOperational retourne false si vu il y a plus de ${STALE_TRACKER_DAYS} jours`, () => {
  assert.equal(isOperational({ lastUpdate: daysAgo(STALE_TRACKER_DAYS + 1) }), false);
});

test('isOperational retourne true si vu dans la fenetre (29j)', () => {
  assert.equal(isOperational({ lastUpdate: daysAgo(29) }), true);
});

// ── healthScore — comportement de base ────────────────────────────────────────

test('healthScore retourne 0 pour un tableau vide', () => {
  assert.equal(healthScore([]), 0);
});

test('healthScore = 80 si connecte + batterie ok mais peson absent', () => {
  const t = { lastUpdate: recent(), lastTrack: { message: { battery_volt: 4.0 } } };
  assert.equal(healthScore([t]), 80);
});

test('healthScore retourne 100 pour un tracker connecte, batterie ok et peson present', () => {
  const t = { lastUpdate: recent(), lastTrack: { message: { battery_volt: 4.0, weight: 1200 } } };
  assert.equal(healthScore([t]), 100);
});

// ── healthScore — correction du biais (cas critiques) ────────────────────────

test('exclut les capteurs jamais deployes (lastUpdate null) du denominateur', () => {
  const actif = { lastUpdate: recent(), lastTrack: { message: { battery_volt: 4.0 } } };
  const mort  = { lastUpdate: null };
  // Sans la correction : (80 + 0) / 2 = 40. Avec la correction : 80 / 1 = 80.
  assert.equal(healthScore([actif, mort]), 80);
});

test('exclut les capteurs silencieux depuis > 30j du denominateur', () => {
  const actif  = { lastUpdate: recent(), lastTrack: { message: { battery_volt: 4.0 } } };
  const ancien = { lastUpdate: daysAgo(60), lastTrack: { message: { battery_volt: 4.0 } } };
  // Sans la correction : (80 + 0) / 2 = 40. Avec la correction : 80 / 1 = 80.
  assert.equal(healthScore([actif, ancien]), 80);
});

test('50 capteurs morts + 3 actifs : score reflète uniquement les 3 actifs', () => {
  const actifs = Array.from({ length: 3 }, () => ({
    lastUpdate: recent(),
    lastTrack:  { message: { battery_volt: 4.0, weight: 500 } },
  }));
  const morts = Array.from({ length: 50 }, () => ({ lastUpdate: null }));
  // Sans correction : (300 + 0) / 53 ≈ 6%. Avec correction : 300/3 = 100.
  assert.equal(healthScore([...actifs, ...morts]), 100);
});

test('retourne 0 si tous les capteurs sont inoperationnels (projet fantome)', () => {
  const morts = [
    { lastUpdate: null },
    { lastUpdate: daysAgo(90) },
    { lastUpdate: daysAgo(45) },
  ];
  assert.equal(healthScore(morts), 0);
});

test('capteur deconnecte mais recent est toujours operationnel (score partiel)', () => {
  const offline = { lastUpdate: daysAgo(2), lastTrack: { message: { battery_volt: 4.0 } } };
  // Vu il y a 2j → opérationnel, mais pas connecté (offlineDelay=60s)
  // score = 0 connexion + 30 batterie = 30
  assert.equal(healthScore([offline]), 30);
});
