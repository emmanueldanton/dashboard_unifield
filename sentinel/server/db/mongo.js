'use strict';
const { MongoClient } = require('mongodb');

let _client = null;
let _db = null;

async function getClient() {
  if (!_client) {
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

module.exports = { getDb, getClient };
