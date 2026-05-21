import os
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from api.loader import load_all_data
from business.alerts import detect_alerts, diff_alerts
from notifications.email import send_alert, build_alert_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ALERTER] %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Credentials UNIFIELD (inchangés, toujours utilisés pour l'API en attendant MongoDB)
UNIFIELD_EMAIL = os.getenv("UNIFIELD_EMAIL", "")
UNIFIELD_KEY   = os.getenv("UNIFIELD_KEY", "")
INTERVAL_MIN   = int(os.getenv("ALERT_INTERVAL_MINUTES", "10"))

# State en mémoire — ids et détails des alertes actives au cycle précédent
_previous_alert_ids: set[str] = set()
_previous_alert_map: dict[str, dict] = {}


def check_and_alert():
    global _previous_alert_ids, _previous_alert_map
    logger.info("Démarrage du cycle de vérification...")

    try:
        data = load_all_data(UNIFIELD_EMAIL, UNIFIELD_KEY)
    except Exception as e:
        logger.error(f"Impossible de charger les données : {e}")
        return

    current_alerts = detect_alerts(data)
    new_issues, resolved_ids = diff_alerts(_previous_alert_ids, current_alerts)

    logger.info(f"Alertes actives : {len(current_alerts)} | Nouvelles : {len(new_issues)} | Résolues : {len(resolved_ids)}")

    if new_issues or resolved_ids:
        # Récupérer le dernier état connu des alertes résolues (noms lisibles)
        resolved_details = [
            {
                "type":    "Résolu",
                "project": _previous_alert_map.get(rid, {}).get("project", rid),
                "detail":  _previous_alert_map.get(rid, {}).get("detail", ""),
            }
            for rid in resolved_ids
        ]

        subject = f"🚨 UNIFIELD — {len(new_issues)} nouveau(x) problème(s)" if new_issues else "✅ UNIFIELD — Problèmes résolus"
        html    = build_alert_html(new_issues, resolved_details)
        sent    = send_alert(subject, html)

        if sent:
            logger.info("Mail d'alerte envoyé avec succès")
        else:
            logger.error("Échec de l'envoi du mail")
    else:
        logger.info("Aucun changement détecté — aucun mail envoyé")

    # Mettre à jour l'état (ids + map complet pour les résolutions futures)
    _previous_alert_ids = {a["id"] for a in current_alerts}
    _previous_alert_map = {a["id"]: a for a in current_alerts}


if __name__ == "__main__":
    logger.info(f"Alerter démarré — vérification toutes les {INTERVAL_MIN} minutes")

    # Premier cycle immédiat au démarrage
    check_and_alert()

    scheduler = BlockingScheduler()
    scheduler.add_job(check_and_alert, "interval", minutes=INTERVAL_MIN)
    scheduler.start()
