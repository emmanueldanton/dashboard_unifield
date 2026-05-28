'use strict';
require('dotenv').config();

const http = require('http');
const path = require('path');

const express = require('express');
const helmet = require('helmet');
const morgan = require('morgan');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const { createProxyMiddleware } = require('http-proxy-middleware');

const PORT         = parseInt(process.env.PORT || '3005', 10);
const BASE_PATH    = (process.env.BASE_PATH || '/unifield').replace(/\/$/, '');
const GUNICORN_URL = process.env.DASH_INTERNAL_URL || 'http://127.0.0.1:8050';

const app = express();

// ── Security headers (CSP off - Dash uses inline scripts) ─────────────────────
app.use(helmet({ contentSecurityPolicy: false }));

// ── Access logging ────────────────────────────────────────────────────────────
app.use(morgan('combined'));

// ── CORS (origins from env, empty = none allowed) ─────────────────────────────
const corsOrigins = process.env.CORS_ORIGINS ? process.env.CORS_ORIGINS.split(',') : [];
app.use(cors({ origin: corsOrigins }));

// ── Static assets (maintenance page only) ────────────────────────────────────
app.use(`${BASE_PATH}/static`, express.static(path.join(__dirname, 'public')));

// ── Cookie helper (manual parse - no cookie-parser dependency) ────────────────
function getUnifieldSid(req) {
  const cookieHeader = req.headers.cookie || '';
  const pair = cookieHeader.split(';').map(s => s.trim()).find(s => s.startsWith('unifield.sid='));
  return pair ? pair.slice('unifield.sid='.length) : null;
}

// ── Rate limiting on login routes ─────────────────────────────────────────────
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(`${BASE_PATH}/auth/login`, loginLimiter);

// ── Health check (public) ─────────────────────────────────────────────────────
app.get(`${BASE_PATH}/health`, (_req, res) => {
  res.json({ status: 'ok', service: 'unifield-node' });
});

// ── Internal status relay (session required) ──────────────────────────────────
app.get(`${BASE_PATH}/status`, (req, res) => {
  if (!getUnifieldSid(req)) return res.redirect(302, `${BASE_PATH}/auth/login`);

  const options = {
    hostname: '127.0.0.1',
    port: 8050,
    path: '/internal/status',
    method: 'GET',
  };
  const probe = http.request(options, (upstream) => {
    let body = '';
    upstream.on('data', chunk => { body += chunk; });
    upstream.on('end', () => {
      try { res.json(JSON.parse(body)); }
      catch { res.status(502).json({ error: 'service_unavailable' }); }
    });
  });
  probe.on('error', () => res.status(502).json({ error: 'service_unavailable' }));
  probe.end();
});

// ── Root redirect ─────────────────────────────────────────────────────────────
app.get(`${BASE_PATH}/`, (_req, res) => {
  res.redirect(302, `${BASE_PATH}/dash/`);
});
app.get(BASE_PATH, (_req, res) => {
  res.redirect(302, `${BASE_PATH}/dash/`);
});

// ── Session guard middleware ───────────────────────────────────────────────────
function requireSession(req, res, next) {
  if (!getUnifieldSid(req)) return res.redirect(302, `${BASE_PATH}/auth/login`);
  next();
}

// ── Proxy factory ─────────────────────────────────────────────────────────────
function makeProxy(opts = {}) {
  return createProxyMiddleware({
    target: GUNICORN_URL,
    changeOrigin: false,
    ...opts,
  });
}

const maintenancePage = path.join(__dirname, 'public', 'maintenance.html');

const dashProxy = makeProxy({
  ws: true,
  on: {
    error: (_err, _req, res) => {
      if (res && !res.headersSent) res.sendFile(maintenancePage);
    },
  },
});

const authProxy = makeProxy();

// ── Auth routes → Gunicorn (no session check) ─────────────────────────────────
app.use(`${BASE_PATH}/auth`, authProxy);

// ── Dash + all other Gunicorn routes (session required) ───────────────────────
app.use(`${BASE_PATH}/dash`, requireSession, dashProxy);
app.use(BASE_PATH,           requireSession, dashProxy);

// ── HTTP server + WebSocket upgrade ───────────────────────────────────────────
const server = app.listen(PORT, () => {
  console.log(JSON.stringify({ event: 'start', port: PORT, base_path: BASE_PATH, target: GUNICORN_URL }));
});

server.on('upgrade', dashProxy.upgrade);
