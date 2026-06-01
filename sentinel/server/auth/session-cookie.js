'use strict';

const COOKIE_NAME = 'sentinel.sid';
const COOKIE_PATH = '/sentinel';

function getCookie(req) {
  const header = req.headers.cookie || '';
  for (const part of header.split(';')) {
    const [name, ...rest] = part.trim().split('=');
    if (name === COOKIE_NAME) return rest.join('=');
  }
  return null;
}

function setCookie(res, sid) {
  const isSecure = process.env.NODE_ENV === 'production';
  let cookie = `${COOKIE_NAME}=${sid}; HttpOnly; SameSite=Lax; Path=${COOKIE_PATH}`;
  if (isSecure) cookie += '; Secure';
  res.setHeader('Set-Cookie', cookie);
}

function clearCookie(res) {
  res.setHeader('Set-Cookie',
    `${COOKIE_NAME}=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax; Path=${COOKIE_PATH}`
  );
}

module.exports = { getCookie, setCookie, clearCookie };
