'use strict';

async function fetchApi(path, options = {}) {
  const res = await fetch(path, { credentials: 'include', ...options });

  if (res.status === 401) {
    document.dispatchEvent(new CustomEvent('sentinel:unauthorized'));
    throw Object.assign(new Error('Session requise'), { code: 'UNAUTHORIZED', status: 401 });
  }

  if (res.status === 403) {
    throw Object.assign(new Error('Acces refuse'), { code: 'FORBIDDEN', status: 403 });
  }

  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).error || ''; } catch { detail = res.statusText; }
    throw Object.assign(new Error(detail || `HTTP ${res.status}`), { status: res.status });
  }

  return res.json();
}

export { fetchApi };
