'use strict';

async function saveSnapshot(db, { connected, disconnected, battery_low, project = null }) {
  await db.collection('snapshots').insertOne({
    ts: new Date(),
    connected,
    disconnected,
    battery_low,
    project,
  });
}

module.exports = { saveSnapshot };
