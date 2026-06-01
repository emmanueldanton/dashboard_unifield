'use strict';
const { Router } = require('express');
const { buildStartUrl, exchangeCode, fetchProfile, revoke } = require('./microsoft-flow');
const { checkRole, NoSentinelRoleError } = require('./role-check');
const { createSession, getSession, deleteSession } = require('./session-store');
const { getCookie, setCookie, clearCookie } = require('./session-cookie');

const router = Router();

const PUBLIC_URL = () => process.env.SENTINEL_PUBLIC_URL || 'http://localhost:3005/sentinel';

router.get('/login', (req, res) => {
  const returnTo = `${PUBLIC_URL()}/auth/complete`;
  res.redirect(buildStartUrl(returnTo));
});

router.get('/complete', async (req, res) => {
  const { auth_code } = req.query;
  if (!auth_code) return res.status(400).send('Missing auth_code');

  try {
    const tokenData = await exchangeCode(auth_code);
    const accessToken = tokenData.access_token || tokenData.accessToken;

    const userInfo = await fetchProfile(accessToken);
    const role = checkRole(userInfo);

    const email = userInfo.email || userInfo.userPrincipalName || '';
    const displayName = userInfo.displayName || userInfo.name || email;

    const sid = createSession(email, role, displayName, accessToken);
    setCookie(res, sid);

    console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'login', user: email, role }));
    res.redirect('/sentinel/');
  } catch (err) {
    if (err instanceof NoSentinelRoleError) {
      return res.status(403).send('<html><body><h2>Acces refuse - aucun role Sentinel</h2></body></html>');
    }
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'auth_error', detail: err.message }));
    res.status(502).send('Erreur auth-api');
  }
});

router.get('/logout', async (req, res) => {
  const sid = getCookie(req);
  if (sid) {
    const session = getSession(sid);
    if (session?.accessToken) {
      revoke(session.accessToken); // best-effort
    }
    deleteSession(sid);
  }
  clearCookie(res);
  res.redirect('/sentinel/auth/login');
});

router.get('/me', (req, res) => {
  const sid = getCookie(req);
  const session = getSession(sid);
  if (!session) return res.status(401).json({ error: 'Session requise', code: 'UNAUTHORIZED' });
  res.json({ email: session.email, displayName: session.displayName, role: session.role });
});

module.exports = router;
