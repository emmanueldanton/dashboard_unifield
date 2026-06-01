'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { filterData, hasData } = require('./flags');

test('hasData : message non vide -> true', () => {
  assert.equal(hasData({ lastTrack: { message: { battery_volt: 3.8 } } }), true);
});

test('hasData : message vide ou absent -> false', () => {
  assert.equal(hasData({ lastTrack: { message: {} } }), false);
  assert.equal(hasData({ lastTrack: {} }), false);
  assert.equal(hasData({}), false);
});

test('filterData exclut les projets parasites (atelier/stock/test/dev)', () => {
  const data = {
    projects: [
      { id: 'p1', name: 'Chantier Lyon' },
      { id: 'p2', name: 'Atelier interne' },   // "atelier" -> parasite
      { id: 'p3', name: 'Banc de TEST' },       // "test" -> parasite (insensible a la casse)
      { id: 'p4', name: 'Pont Marseille' },
    ],
    trackers: [
      { _project_id: 'p1', lastTrack: { message: { battery_volt: 3.8 } } },
      { _project_id: 'p2', lastTrack: { message: { battery_volt: 3.9 } } },
    ],
    project_data: {
      p1: { trackers: [{ lastTrack: { message: { battery_volt: 3.8 } } }] },
      p2: { trackers: [{ lastTrack: { message: { battery_volt: 3.9 } } }] },
    },
  };
  const out = filterData(data);
  assert.deepEqual(out.projects.map(p => p.id), ['p1', 'p4']);
  assert.equal(out.trackers.length, 1);
  assert.equal(out.trackers[0]._project_id, 'p1');
  assert.ok(out.project_data.p1);
  assert.ok(!out.project_data.p2);
});

test('filterData retire les trackers sans donnees', () => {
  const data = {
    projects: [{ id: 'p1', name: 'Chantier' }],
    trackers: [
      { _project_id: 'p1', lastTrack: { message: { battery_volt: 3.8 } } },
      { _project_id: 'p1', lastTrack: { message: {} } },
    ],
    project_data: {},
  };
  const out = filterData(data);
  assert.equal(out.trackers.length, 1);
});
