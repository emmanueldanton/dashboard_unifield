'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mapRoles, checkRole, NoSentinelRoleError } = require('./role-check');

test('mapRoles retourne admin pour app:sentinel:admin', () => {
  assert.equal(mapRoles({ roles: ['app:sentinel:admin'] }), 'app:sentinel:admin');
});

test('mapRoles retourne read pour app:sentinel:read', () => {
  assert.equal(mapRoles({ roles: ['app:sentinel:read'] }), 'app:sentinel:read');
});

test('mapRoles retourne write pour app:sentinel:write', () => {
  assert.equal(mapRoles({ roles: ['app:sentinel:write'] }), 'app:sentinel:write');
});

test('mapRoles retourne null si aucun role sentinel', () => {
  assert.equal(mapRoles({ roles: ['app:soc:admin', 'app:siem:read'] }), null);
});

test('mapRoles retourne null si roles absent', () => {
  assert.equal(mapRoles({}), null);
});

test('checkRole leve NoSentinelRoleError si aucun role sentinel', () => {
  assert.throws(
    () => checkRole({ roles: [] }),
    (err) => err instanceof NoSentinelRoleError
  );
});

test('checkRole retourne le role quand valide', () => {
  assert.equal(checkRole({ roles: ['app:sentinel:admin'] }), 'app:sentinel:admin');
});
