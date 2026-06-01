'use strict';

// Port exact de business/schedule.py

const DAYS_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const WD_MAP = { Mon: 'mon', Tue: 'tue', Wed: 'wed', Thu: 'thu', Fri: 'fri', Sat: 'sat', Sun: 'sun' };

function parseSchedule(schedule) {
  if (!schedule || (typeof schedule === 'object' && Object.keys(schedule).length === 0)) return null;

  const result = {};
  let hasRealSchedule = false;

  for (const day of DAYS_ORDER) {
    const cfg = schedule[day];

    if (cfg && typeof cfg === 'object' && !Array.isArray(cfg)) {
      const enable = cfg.enable === true;
      const times = Array.isArray(cfg.times) ? cfg.times : [];
      const isH24 = times.some(s => Array.isArray(s) && s.length >= 2 &&
        s[0] === '00:00' && (s[1] === '23:59' || s[1] === '24:00'));
      if (enable && times.length && !isH24) hasRealSchedule = true;
      result[day] = { enable, times, h24: isH24 };

    } else if (Array.isArray(cfg) && cfg.length >= 2) {
      const enable = cfg.length > 2 ? String(cfg[2]).toLowerCase() === 'true' : true;
      const times = (cfg[0] && cfg[1]) ? [[cfg[0], cfg[1]]] : [];
      const isH24 = cfg[0] === '00:00' && (cfg[1] === '23:59' || cfg[1] === '24:00');
      if (enable && times.length && !isH24) hasRealSchedule = true;
      result[day] = { enable, times, h24: isH24 };

    } else {
      result[day] = { enable: false, times: [], h24: false };
    }
  }

  return hasRealSchedule ? result : null;
}

// Renvoie { dayKey, hhmm } pour `now` dans le fuseau tzStr (Europe/Paris par defaut cote Python).
function localParts(now, tzStr) {
  const tz = tzStr || 'UTC';
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(now);
    const wd = parts.find(p => p.type === 'weekday')?.value || 'Mon';
    const hh = parts.find(p => p.type === 'hour')?.value || '00';
    const mm = parts.find(p => p.type === 'minute')?.value || '00';
    return { dayKey: WD_MAP[wd] || 'mon', hhmm: `${hh}:${mm}` };
  } catch {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(now);
    const wd = parts.find(p => p.type === 'weekday')?.value || 'Mon';
    const hh = parts.find(p => p.type === 'hour')?.value || '00';
    const mm = parts.find(p => p.type === 'minute')?.value || '00';
    return { dayKey: WD_MAP[wd] || 'mon', hhmm: `${hh}:${mm}` };
  }
}

function isTimeInSchedule(dayKey, hhmm, parsedSchedule) {
  if (parsedSchedule === null) return true;
  const dayCfg = parsedSchedule[dayKey] || {};
  if (dayCfg.h24) return true;
  if (!dayCfg.enable) return false;
  for (const slot of dayCfg.times || []) {
    if (Array.isArray(slot) && slot.length >= 2 && slot[0] <= hhmm && hhmm <= slot[1]) return true;
  }
  return false;
}

// Retourne [horsSchedule, manquants] (port de check_schedule_anomalies).
function checkScheduleAnomalies(trackers, schedule, now, tzStr = 'UTC', activitySec = 86400) {
  const parsed = parseSchedule(schedule);
  if (parsed === null) return [[], []];

  const { dayKey, hhmm } = localParts(now, tzStr);
  const inScheduleNow = isTimeInSchedule(dayKey, hhmm, parsed);

  const horsSchedule = [];
  const manquants = [];

  for (const t of trackers) {
    const connected = t._is_connected === true || t._isConnected === true;
    const lastSec = t._last_seen_seconds ?? t._lastSeenSeconds ?? -1;

    if (inScheduleNow) {
      const hasWeight = t._weight_status === 'ok';
      const recentlyActive = lastSec >= 0 && lastSec < activitySec;
      if (!connected && hasWeight && recentlyActive) manquants.push(t);
    } else {
      if (connected || (lastSec >= 0 && lastSec < 3600)) horsSchedule.push(t);
    }
  }

  return [horsSchedule, manquants];
}

module.exports = { parseSchedule, isTimeInSchedule, checkScheduleAnomalies };
