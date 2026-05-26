import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from api.loader import load_all_data
from business.alerts import detect_alerts, diff_alerts
from notifications.email import send_alert, build_alert_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ALERTER] %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

UNIFIELD_EMAIL = os.getenv("UNIFIELD_EMAIL", "")
UNIFIELD_KEY   = os.getenv("UNIFIELD_KEY", "")
INTERVAL_MIN   = int(os.getenv("ALERT_INTERVAL_MINUTES", "10"))

_previous_alert_ids: set[str] = set()


def _write_alert_history(subject: str, issues_count: int, recipients: list[str],
                         mailgun_status: str) -> None:
    """Write one document to MongoDB alert_history after each alert send.

    Errors are silently logged — a write failure must never crash the alerter.
    """
    try:
        from api.mongo_client import get_db
        db = get_db()
        db["alert_history"].insert_one({
            "ts":             datetime.now(timezone.utc),
            "subject":        subject,
            "issues_count":   issues_count,
            "recipients":     recipients,
            "mailgun_status": mailgun_status,
        })
        logger.info('{"event": "alert_history_written", "subject": "%s"}', subject[:80])
    except Exception as exc:
        logger.warning('{"event": "alert_history_failed", "detail": "%s"}', str(exc)[:120])


def _get_recipients() -> list[str]:
    raw = os.getenv("ALERT_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def check_and_alert():
    global _previous_alert_ids
    logger.info("Démarrage du cycle de vérification...")

    try:
        data = load_all_data(UNIFIELD_EMAIL, UNIFIELD_KEY)
    except Exception as e:
        logger.error('{"event": "alerter_load_failed", "detail": "%s"}', str(e)[:200])
        return

    current_alerts = detect_alerts(data)
    new_issues, resolved_ids = diff_alerts(_previous_alert_ids, current_alerts)

    logger.info("Alertes actives : %d | Nouvelles : %d | Résolues : %d",
                len(current_alerts), len(new_issues), len(resolved_ids))

    if new_issues or resolved_ids:
        resolved_details = [
            {"type": "Résolu", "project": rid, "detail": ""}
            for rid in resolved_ids
        ]

        subject = (
            f"UNIFIELD — {len(new_issues)} nouveau(x) problème(s)" if new_issues
            else "UNIFIELD — Problèmes résolus"
        )
        html = build_alert_html(new_issues, resolved_details)
        sent = send_alert(subject, html)

        mailgun_status = "sent" if sent else "failed"
        if sent:
            logger.info('{"event": "alert_sent", "subject": "%s"}', subject[:80])
        else:
            logger.error('{"event": "alert_failed", "subject": "%s"}', subject[:80])

        _write_alert_history(
            subject=subject,
            issues_count=len(new_issues),
            recipients=_get_recipients(),
            mailgun_status=mailgun_status,
        )
    else:
        logger.info("Aucun changement détecté — aucun mail envoyé")

    _previous_alert_ids = {a["id"] for a in current_alerts}


if __name__ == "__main__":
    logger.info("Alerter démarré — vérification toutes les %d minutes", INTERVAL_MIN)
    check_and_alert()
    scheduler = BlockingScheduler()
    scheduler.add_job(check_and_alert, "interval", minutes=INTERVAL_MIN)
    scheduler.start()
