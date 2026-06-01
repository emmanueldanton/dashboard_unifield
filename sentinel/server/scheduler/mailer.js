'use strict';
const mailgun = require('mailgun-js');

function getMailer() {
  return mailgun({
    apiKey: process.env.MAILGUN_API_KEY,
    domain: process.env.MAILGUN_DOMAIN,
    host: 'api.eu.mailgun.net',
  });
}

async function sendAlert(alerts) {
  if (!alerts || alerts.length === 0) return;

  const recipients = process.env.ALERT_RECIPIENTS || '';
  if (!recipients) return;

  const byProject = {};
  for (const a of alerts) {
    const key = a.projectName || 'Sans projet';
    if (!byProject[key]) byProject[key] = [];
    byProject[key].push(a);
  }

  const lines = [];
  for (const [project, projectAlerts] of Object.entries(byProject)) {
    lines.push(`=== ${project} ===`);
    for (const a of projectAlerts) {
      lines.push(`[${a.severity.toUpperCase()}] ${a.message}`);
    }
  }

  const data = {
    from: `Sentinel <sentinel@${process.env.MAILGUN_DOMAIN}>`,
    to: recipients,
    subject: `Sentinel - ${alerts.length} alerte(s) detectee(s)`,
    text: lines.join('\n'),
  };

  try {
    const mg = getMailer();
    await mg.messages().send(data);
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'mailer_error', detail: err.message }));
  }
}

async function writeHistory(db, alerts) {
  if (!alerts || alerts.length === 0) return;
  const now = new Date();
  const docs = alerts.map(a => ({ ...a, ts: now }));
  try {
    await db.collection('alert_history').insertMany(docs);
  } catch (err) {
    console.error(JSON.stringify({ ts: new Date().toISOString(), event: 'history_write_error', detail: err.message }));
  }
}

module.exports = { sendAlert, writeHistory };
