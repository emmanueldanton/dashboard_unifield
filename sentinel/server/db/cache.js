'use strict';

// Port de cache.py : cache memoire singleton du chargement MongoDB.
// Precharge au demarrage (avant toute connexion utilisateur), rafraichi
// periodiquement. Tous les endpoints data lisent ce cache au lieu d'appeler
// loadAllData() a chaque requete -> reponses instantanees + affichage stable.

const { loadAllData } = require('./loader');

let _data = null;          // dernier snapshot {projects, trackers, project_data, loaded_at}
let _loadedAt = null;      // ms epoch du dernier succes
let _mongoOk = true;       // false si le dernier refresh a echoue (on garde _data precedent)
let _version = 0;          // incremente a chaque refresh reussi
let _inflight = null;      // promesse du refresh en cours (anti-concurrence)
let _timer = null;

async function refresh() {
  if (_inflight) return _inflight;   // un seul refresh a la fois, promesse partagee
  _inflight = (async () => {
    try {
      const data = await loadAllData();
      _data = data;
      _loadedAt = Date.now();
      _version += 1;
      _mongoOk = true;
      console.log(JSON.stringify({
        ts: new Date().toISOString(), event: 'cache_refresh',
        version: _version, projects: data.projects.length, trackers: data.trackers.length,
      }));
    } catch (err) {
      // Degradation gracieuse : on conserve _data precedent, on signale juste l'etat.
      _mongoOk = false;
      console.error(JSON.stringify({
        ts: new Date().toISOString(), event: 'cache_refresh_failed', detail: err.message,
      }));
    } finally {
      _inflight = null;
    }
  })();
  return _inflight;
}

// Donnees en cache ; declenche (et attend) un premier chargement si vide (cold start).
async function getData() {
  if (_data) return _data;
  await refresh();
  return _data;
}

function getCachedData() { return _data; }

function getCacheMeta() {
  return { loadedAt: _loadedAt, mongoOk: _mongoOk, version: _version, loading: _inflight !== null };
}

// Precharge immediat + rafraichissement periodique (defaut 15 min, comme le
// dashboard Python interval-15min). Surchargeable via CACHE_REFRESH_SEC.
function startCache() {
  const sec = Math.max(10, parseInt(process.env.CACHE_REFRESH_SEC || '900', 10));
  refresh(); // preload au demarrage, avant toute connexion
  if (_timer) clearInterval(_timer);
  _timer = setInterval(refresh, sec * 1000);
  if (_timer.unref) _timer.unref();
  console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'cache_started', interval_sec: sec }));
  return _timer;
}

module.exports = { refresh, getData, getCachedData, getCacheMeta, startCache };
