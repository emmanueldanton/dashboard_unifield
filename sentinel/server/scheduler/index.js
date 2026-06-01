'use strict';
const cron = require('node-cron');
const { runCycle } = require('./collector');

let isRunning = false;
let lastCycle = null;
let nextCycle = null;

const previousState = new Map();

function getSchedulerState() {
  return { isRunning, lastCycle, nextCycle };
}

function startScheduler(db) {
  const intervalMin = parseInt(process.env.ALERT_INTERVAL_MIN || '10', 10);
  const cronExpr = `*/${intervalMin} * * * *`;

  const job = cron.schedule(cronExpr, async () => {
    if (isRunning) {
      console.log(JSON.stringify({ ts: new Date().toISOString(), event: 'cycle_skip', reason: 'already_running' }));
      return;
    }
    isRunning = true;
    lastCycle = new Date().toISOString();
    try {
      await runCycle(db, previousState);
    } finally {
      isRunning = false;
      const next = new Date(Date.now() + intervalMin * 60 * 1000);
      nextCycle = next.toISOString();
    }
  });

  // First cycle after 2s
  setTimeout(async () => {
    if (isRunning) return;
    isRunning = true;
    lastCycle = new Date().toISOString();
    try {
      await runCycle(db, previousState);
    } finally {
      isRunning = false;
      const next = new Date(Date.now() + intervalMin * 60 * 1000);
      nextCycle = next.toISOString();
    }
  }, 2000);

  return job;
}

module.exports = { startScheduler, getSchedulerState };
