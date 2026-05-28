import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Seuils configurables via variables d'environnement (avec valeurs par défaut)
import os
DISCONNECT_THRESHOLD_HOURS = int(os.getenv("DISCONNECT_THRESHOLD_HOURS", "2"))
BATTERY_THRESHOLD_PERCENT  = float(os.getenv("BATTERY_THRESHOLD_PERCENT", "20"))
ENDING_SOON_DAYS           = int(os.getenv("ENDING_SOON_DAYS", "7"))


def detect_alerts(data: dict) -> list[dict]:
    """
    Analyse les données du cache et retourne une liste d'alertes actives.
    Chaque alerte est un dict : {id, type, project, detail, severity}
    """
    alerts = []
    trackers = data.get("all_trackers", [])
    now = datetime.now(timezone.utc)

    for tracker in trackers:
        project  = tracker.get("_project_name", "Projet inconnu")
        unit     = tracker.get("_unit_name", "")
        label    = f"{project} - {unit}" if unit else project
        t_id     = tracker.get("id", tracker.get("_id", ""))

        # Capteur déconnecté
        last_seen_seconds = tracker.get("_last_seen_seconds", -1)
        if last_seen_seconds >= 0 and last_seen_seconds > DISCONNECT_THRESHOLD_HOURS * 3600:
            hours = round(last_seen_seconds / 3600, 1)
            alerts.append({
                "id":       f"offline_{t_id}",
                "type":     "Capteur hors ligne",
                "project":  label,
                "detail":   f"Dernière communication : il y a {hours}h",
                "severity": "critique",
            })

        # Batterie faible
        battery = tracker.get("_battery_percent", None)
        if battery is not None and battery < BATTERY_THRESHOLD_PERCENT:
            alerts.append({
                "id":       f"battery_{t_id}",
                "type":     "Batterie faible",
                "project":  label,
                "detail":   f"Niveau batterie : {battery:.0f}%",
                "severity": "warning",
            })

    # Projets en anomalie (endDate dépassée)
    projects = data.get("projects", [])
    for proj in projects:
        proj_name = proj.get("name", proj.get("_id", "Inconnu"))
        proj_id   = str(proj.get("_id", proj_name))
        end_date  = proj.get("endDate", None)

        if end_date:
            try:
                if isinstance(end_date, str):
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                else:
                    end_dt = end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date

                delta_days = (end_dt - now).days

                if delta_days < 0 and proj.get("isActive", False):
                    alerts.append({
                        "id":       f"overdue_{proj_id}",
                        "type":     "Projet en anomalie",
                        "project":  proj_name,
                        "detail":   f"Date de fin dépassée depuis {abs(delta_days)} jours",
                        "severity": "critique",
                    })
                elif 0 <= delta_days <= ENDING_SOON_DAYS:
                    alerts.append({
                        "id":       f"ending_{proj_id}",
                        "type":     "Fin imminente",
                        "project":  proj_name,
                        "detail":   f"Se termine dans {delta_days} jour(s)",
                        "severity": "warning",
                    })
            except Exception as e:
                logger.warning(f"Impossible de parser endDate pour {proj_name} : {e}")

    return alerts


def diff_alerts(previous: set, current: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Compare l'état précédent et l'état actuel.
    Retourne (nouvelles_alertes, ids_resolus)
    """
    current_ids = {a["id"] for a in current}
    current_map = {a["id"]: a for a in current}

    new_issues = [current_map[aid] for aid in current_ids if aid not in previous]
    resolved   = [aid for aid in previous if aid not in current_ids]

    return new_issues, resolved
