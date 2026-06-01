'use strict';
const crypto = require('crypto');

const SESSION_TTL = 86400; // 24h in seconds
const _sessions = new Map();

function _hash(sid) {
  return crypto.createHash('sha256').update(sid).digest('hex');
}

function createSession(email, role, displayName, accessToken) {
  const sid = crypto.randomBytes(32).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  _sessions.set(_hash(sid), {
    email,
    displayName: displayName || email,
    role,
    accessToken,
    createdAt: now,
    expiresAt: now + SESSION_TTL,
  });
  return sid;
}

function getSession(sid) {
  if (!sid) return null;
  const session = _sessions.get(_hash(sid));
  if (!session) return null;
  if (session.expiresAt < Math.floor(Date.now() / 1000)) {
    _sessions.delete(_hash(sid));
    return null;
  }
  return session;
}

function deleteSession(sid) {
  if (!sid) return;
  _sessions.delete(_hash(sid));
}

function cleanupExpired() {
  const now = Math.floor(Date.now() / 1000);
  let removed = 0;
  for (const [key, session] of _sessions) {
    if (session.expiresAt < now) {
      _sessions.delete(key);
      removed++;
    }
  }
  if (removed > 0) {
    console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'session_cleanup', removed }));
  }
}

setInterval(cleanupExpired, 3600 * 1000);

module.exports = { createSession, getSession, deleteSession };
