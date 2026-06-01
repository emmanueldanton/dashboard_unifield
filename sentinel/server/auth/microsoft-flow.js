'use strict';

function buildStartUrl(returnTo) {
  const base = process.env.AUTH_API_BASE_URL;
  const consumer = process.env.AUTH_API_SERVICE_CONSUMER_NAME || 'sentinel';
  const params = new URLSearchParams({ consumer, returnTo });
  return `${base}/v1/auth/microsoft/start?${params}`;
}

async function exchangeCode(authCode) {
  const base = process.env.AUTH_API_BASE_URL;
  const consumer = process.env.AUTH_API_SERVICE_CONSUMER_NAME || 'sentinel';
  const secret = process.env.AUTH_API_SERVICE_CONSUMER_SECRET;

  const res = await fetch(`${base}/v1/auth/code/exchange`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `ServiceConsumer ${consumer}:${secret}`,
    },
    body: JSON.stringify({ code: authCode }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw Object.assign(new Error(`auth-api exchange failed: ${res.status}`), { status: res.status, detail: err });
  }

  return res.json();
}

async function fetchProfile(accessToken) {
  const base = process.env.AUTH_API_BASE_URL;

  const res = await fetch(`${base}/v1/users/me`, {
    headers: { 'Authorization': `Bearer ${accessToken}` },
  });

  if (!res.ok) {
    throw Object.assign(new Error(`auth-api profile failed: ${res.status}`), { status: res.status });
  }

  return res.json();
}

async function revoke(accessToken) {
  const base = process.env.AUTH_API_BASE_URL;
  try {
    await fetch(`${base}/v1/auth/logout`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${accessToken}` },
    });
  } catch {
    // best-effort
  }
}

module.exports = { buildStartUrl, exchangeCode, fetchProfile, revoke };
