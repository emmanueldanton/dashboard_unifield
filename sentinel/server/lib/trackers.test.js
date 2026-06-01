'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { isConnected, batteryVolt, batteryStatus, lastSeenSeconds, healthScore } = require('./trackers');

test('isConnected retourne false si lastUpdate est null', () => {
  assert.equal(isConnected({ lastUpdate: null }), false);
});

test('isConnected retourne false si lastUpdate est undefined', () => {
  assert.equal(isConnected({}), false);
});

test('isConnected retourne true si lastUpdate recente (< 60s)', () => {
  const recent = new Date(Date.now() - 10 * 1000).toISOString();
  assert.equal(isConnected({ lastUpdate: recent }), true);
});

test('isConnected retourne false si lastUpdate ancienne (> 60s)', () => {
  const old = new Date(Date.now() - 120 * 1000).toISOString();
  assert.equal(isConnected({ lastUpdate: old }), false);
});

test('batteryVolt extrait depuis lastTrack.message.battery_volt', () => {
  const t = { lastTrack: { message: { battery_volt: 3.8 } } };
  assert.equal(batteryVolt(t), 3.8);
});

test('batteryVolt retourne -1 si absent', () => {
  assert.equal(batteryVolt({}), -1);
  assert.equal(batteryVolt({ lastTrack: {} }), -1);
  assert.equal(batteryVolt({ lastTrack: { message: {} } }), -1);
});

test('batteryStatus retourne "faible" en dessous de 3.5V', () => {
  const t = { lastTrack: { message: { battery_volt: 3.2 } } };
  assert.equal(batteryStatus(t), 'faible');
});

test('batteryStatus retourne "ok" a 3.5V et au dessus', () => {
  const t = { lastTrack: { message: { battery_volt: 3.7 } } };
  assert.equal(batteryStatus(t), 'ok');
});

test('batteryStatus retourne "inconnu" si battery_volt absent', () => {
  assert.equal(batteryStatus({}), 'inconnu');
});

test('healthScore retourne 0 pour un tableau vide', () => {
  assert.equal(healthScore([]), 0);
});

test('healthScore retourne 100 pour un tracker parfaitement connecte avec bonne batterie', () => {
  const recent = new Date(Date.now() - 5 * 1000).toISOString();
  const t = { lastUpdate: recent, lastTrack: { message: { battery_volt: 4.0 } } };
  const score = healthScore([t]);
  assert.ok(score > 90, `Score attendu > 90, obtenu ${score}`);
});
