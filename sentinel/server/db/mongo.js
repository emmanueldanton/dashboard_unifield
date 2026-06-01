'use strict';
const { MongoClient } = require('mongodb');

let _client = null;
let _db = null;

async function getClient() {
  if (!_client) {
    if (!process.env.MONGO_URI) throw new Error('MONGO_URI non definie dans .env');
    _client = new MongoClient(process.env.MONGO_URI, {
      maxPoolSize: 20,
      minPoolSize: 3,
      connectTimeoutMS: 10000,
      socketTimeoutMS: 15000,
    });
    await _client.connect();
  }
  return _client;
}

async function getDb() {
  if (!_db) {
    const client = await getClient();
    _db = client.db(process.env.MONGO_DB || 'unifield');
  }
  return _db;
}

// Base dédiée aux collections en écriture Sentinel (snapshots, alert_history, alert_rules)
async function getSentinelDb() {
  const client = await getClient();
  return client.db(process.env.SENTINEL_DB || 'cad42Users');
}

module.exports = { getDb, getClient, getSentinelDb };
