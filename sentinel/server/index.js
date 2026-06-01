'use strict';
require('dotenv').config();

const path = require('path');
const express = require('express');
const helmet = require('helmet');
const morgan = require('morgan');
const cors = require('cors');
const rateLimit = require('express-rate-limit');

const authRouter = require('./auth/routes');
const { getCookie, setCookie } = require('./auth/session-cookie');
const { getSession } = require('./auth/session-store');

const app = express();
const BASE = process.env.BASE_PATH || '/sentinel';
const PORT = parseInt(process.env.PORT || '3005', 10);

app.use(helmet({ contentSecurityPolicy: false }));
app.use(morgan('combined'));
app.use(express.json());
app.use(cors({ origin: false }));

// Health check - public
app.get(`${BASE}/health`, (_req, res) => {
  res.json({ status: 'ok', service: 'sentinel' });
});

// Auth routes - public (no guard)
const loginLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 10 });
app.use(`${BASE}/auth/login`, loginLimiter);
app.use(`${BASE}/auth`, authRouter);

// Dev bypass
function isBypass() {
  return process.env.SENTINEL_DEV_AUTH_BYPASS === 'true' && process.env.NODE_ENV !== 'production';
}

// Auth guard middleware for all other /sentinel/* routes
app.use(`${BASE}`, (req, res, next) => {
  // Skip auth routes (already handled) and health
  if (req.path.startsWith('/auth/') || req.path === '/health') return next();

  if (isBypass()) return next();

  const sid = getCookie(req);
  const session = getSession(sid);

  if (!session) {
    const isApiOrFetch = req.path.startsWith('/api/') || req.headers.accept?.includes('application/json');
    if (isApiOrFetch) {
      return res.status(401).json({ error: 'Session requise', code: 'UNAUTHORIZED' });
    }
    return res.redirect(`${BASE}/auth/login`);
  }

  req.session = session;
  next();
});

// API routers (mounted after guard)
app.use(`${BASE}/api/kpis`, require('./api/kpis'));
app.use(`${BASE}/api/snapshots`, require('./api/snapshots'));
app.use(`${BASE}/api/trackers`, require('./api/trackers'));
app.use(`${BASE}/api/projects`, require('./api/projects'));
app.use(`${BASE}/api/alert-history`, require('./api/alerts').historyRouter);
app.use(`${BASE}/api/alert-status`, require('./api/alerts').statusRouter);
app.use(`${BASE}/api/rules`, require('./api/rules'));

// Serve frontend static (production)
const distDir = path.join(__dirname, '..', 'frontend', 'dist');
app.use(`${BASE}`, express.static(distDir));

// SPA fallback
app.get(`${BASE}/*`, (_req, res) => {
  res.sendFile(path.join(distDir, 'index.html'));
});

async function start() {
  const { getDb } = require('./db/mongo');
  const { startScheduler } = require('./scheduler/index');

  try {
    const db = await getDb();
    startScheduler(db);
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'startup_db_error', detail: err.message }));
  }

  app.listen(PORT, () => {
    console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'server_start', port: PORT, base: BASE }));
  });
}

start();
