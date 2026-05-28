import os
import requests
import logging

logger = logging.getLogger(__name__)

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN  = os.getenv("MAILGUN_DOMAIN", "api.cad42.com")
MAILGUN_API_URL = os.getenv("MAILGUN_API_URL", "https://api.eu.mailgun.net")
MAILGUN_FROM    = os.getenv("MAILGUN_FROM", "workflow@api.cad42.com")
ALERT_RECIPIENTS = os.getenv("ALERT_RECIPIENTS", "")  # emails séparés par virgule


def send_alert(subject: str, html_body: str, recipients: list[str] = None) -> bool:
    """
    Envoie un mail d'alerte via l'API Mailgun (région EU).
    Retourne True si l'envoi a réussi, False sinon.
    """
    if not MAILGUN_API_KEY:
        logger.error("MAILGUN_API_KEY non définie - mail non envoyé")
        return False

    if recipients is None:
        recipients = [r.strip() for r in ALERT_RECIPIENTS.split(",") if r.strip()]

    if not recipients:
        logger.error("Aucun destinataire défini - mail non envoyé")
        return False

    try:
        response = requests.post(
            f"{MAILGUN_API_URL}/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from":    f"CAD42 Alerts <{MAILGUN_FROM}>",
                "to":      recipients,
                "subject": subject,
                "html":    html_body,
            },
            timeout=10,
        )
        if response.status_code == 200:
            logger.info(f"Mail envoyé : {subject} → {recipients}")
            return True
        else:
            logger.error(f"Mailgun erreur {response.status_code} : {response.text}")
            return False
    except requests.RequestException as e:
        logger.error(f"Erreur réseau Mailgun : {e}")
        return False


def build_alert_html(new_issues: list[dict], resolved: list[dict]) -> str:
    """
    Construit le corps HTML du mail d'alerte.
    """
    rows_new = "".join(
        f"""<tr>
            <td style='padding:8px;border-bottom:1px solid #333;color:#ff4d4d;'>🔴 {issue['type']}</td>
            <td style='padding:8px;border-bottom:1px solid #333;'>{issue['project']}</td>
            <td style='padding:8px;border-bottom:1px solid #333;color:#aaa;'>{issue.get('detail', '')}</td>
        </tr>"""
        for issue in new_issues
    )

    rows_resolved = "".join(
        f"""<tr>
            <td style='padding:8px;border-bottom:1px solid #333;color:#4dff88;'>✅ Résolu</td>
            <td style='padding:8px;border-bottom:1px solid #333;'>{issue['project']}</td>
            <td style='padding:8px;border-bottom:1px solid #333;color:#aaa;'>{issue.get('detail', '')}</td>
        </tr>"""
        for issue in resolved
    )

    return f"""
    <html>
    <body style='font-family:sans-serif;background:#1a1a1a;color:#e0e0e0;padding:24px;'>
        <h2 style='color:#ffffff;'>🚨 Alerte UNIFIELD - Changement d'état détecté</h2>

        {'<h3 style="color:#ff4d4d;">Nouveaux problèmes</h3><table style="width:100%;border-collapse:collapse;"><tr><th style="text-align:left;padding:8px;background:#2a2a2a;">Type</th><th style="text-align:left;padding:8px;background:#2a2a2a;">Projet</th><th style="text-align:left;padding:8px;background:#2a2a2a;">Détail</th></tr>' + rows_new + '</table>' if new_issues else ''}

        {'<h3 style="color:#4dff88;margin-top:24px;">Problèmes résolus</h3><table style="width:100%;border-collapse:collapse;"><tr><th style="text-align:left;padding:8px;background:#2a2a2a;">Type</th><th style="text-align:left;padding:8px;background:#2a2a2a;">Projet</th><th style="text-align:left;padding:8px;background:#2a2a2a;">Détail</th></tr>' + rows_resolved + '</table>' if resolved else ''}

        <p style='color:#666;margin-top:32px;font-size:12px;'>CAD42 Dashboard UNIFIELD - Système d'alertes automatiques</p>
    </body>
    </html>
    """
