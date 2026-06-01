'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { computeSegments } = require('./segments');

const now = new Date('2026-06-01T12:00:00Z');
const inDays = d => new Date(now.getTime() + d * 86400000).toISOString();

// project_data : {pid: {trackers: [{_last_seen_seconds}]}}
function pd(map) { return map; }

test('actif = au moins un tracker vu il y a moins de activitySec', () => {
  const projects = [{ id: 'p1', endDate: inDays(100) }];
  const data = pd({ p1: { trackers: [{ _last_seen_seconds: 30 }] } });
  const segs = computeSegments(projects, data, now, 60, 30, 10);
  assert.equal(segs.active.length, 1);
});

test('pas de signal -> non actif', () => {
  const projects = [{ id: 'p1', endDate: inDays(100) }];
  const data = pd({ p1: { trackers: [{ _last_seen_seconds: 120 }] } });
  const segs = computeSegments(projects, data, now, 60, 30, 10);
  assert.equal(segs.active.length, 0);
  assert.equal(segs.total.length, 1);
});

test('fin imminente = 0 < jours < endingDays (strict)', () => {
  const projects = [
    { id: 'a', endDate: inDays(5) },   // dans ending
    { id: 'b', endDate: inDays(30) },  // == endingDays -> exclu (strict)
    { id: 'c', endDate: inDays(60) },  // hors fenetre
  ];
  const segs = computeSegments(projects, {}, now, 60, 30, 10);
  assert.deepEqual(segs.ending.map(p => p.id), ['a']);
});

test('termine (past) = endDate depassee et non archive', () => {
  const projects = [{ id: 'p1', endDate: inDays(-3) }];
  const segs = computeSegments(projects, {}, now, 60, 30, 10);
  assert.equal(segs.past.length, 1);
  assert.equal(segs.total.length, 0);
});

test('archive sort des autres buckets', () => {
  const projects = [{ id: 'p1', endDate: inDays(-3), archived: true }];
  const segs = computeSegments(projects, {}, now, 60, 30, 10);
  assert.equal(segs.archived.length, 1);
  assert.equal(segs.past.length, 0);
});

test('anomalie = projet termine mais encore actif', () => {
  const projects = [{ id: 'p1', endDate: inDays(-3) }];
  const data = pd({ p1: { trackers: [{ _last_seen_seconds: 10 }] } });
  const segs = computeSegments(projects, data, now, 60, 30, 10);
  assert.equal(segs.past.length, 1);
  assert.equal(segs.active.length, 1);
  assert.equal(segs.anomalies.length, 1);
});
