from __future__ import annotations
import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ───────────────────────────────────────────────────────────────────
UNIFIELD_MONGO_URI = os.environ.get("UNIFIELD_MONGO_URI", "")
UNIFIELD_MONGO_DB  = os.environ.get("UNIFIELD_MONGO_DB", "unifield")

# ── Application ───────────────────────────────────────────────────────────────
BASE_PATH  = os.environ.get("BASE_PATH", "/unifield/")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8050")
APP_ENV    = os.environ.get("APP_ENV", "production")

# ── Auth bypass (dev uniquement) ──────────────────────────────────────────────
UNIFIELD_DEV_AUTH_BYPASS = os.environ.get("UNIFIELD_DEV_AUTH_BYPASS", "false").lower() == "true"

# ── Auth SSO ──────────────────────────────────────────────────────────────────
AUTH_API_BASE_URL               = os.environ.get("AUTH_API_BASE_URL", "")
AUTH_API_SERVICE_CONSUMER_SECRET = os.environ.get("AUTH_API_SERVICE_CONSUMER_SECRET", "")

# ── Mailgun ───────────────────────────────────────────────────────────────────
MAILGUN_API_KEY             = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_WEBHOOK_SIGNING_KEY = os.environ.get("MAILGUN_WEBHOOK_SIGNING_KEY", "")

# ── Seuils métier ─────────────────────────────────────────────────────────────
BATTERY_WARNING_THRESHOLD = 3.5
ENDING_SOON_DAYS          = 30
PAST_DAYS                 = 10

# Fenêtre d'activité MongoDB : une base est "active" si au moins un tracker
# a envoyé un lastUpdate dans les ACTIVITY_WINDOW_SECONDS précédant le dernier
# chargement (aligné sur le critère Phase 1 → Phase 2 de mongo_loader.py).
ACTIVITY_WINDOW_SECONDS = 60

PARASITE_KEYWORDS = {"atelier", "stock", "test", "dev"}

PARIS_TZ = ZoneInfo("Europe/Paris")

# ── Palette Z42 dark cyber ────────────────────────────────────────────────────
C = {
    "accent":     "#7DC242", "accent_bg":  "#0f1a0a",
    "bg":         "#0a0a0a", "surface":    "#111111", "border":    "#1e2a1a",
    "text":       "#E8F5E1", "text_muted": "#7a9a6a", "text_light": "#4a6a3a",
    "red":        "#DC2626", "red_bg":     "#1a0a0a", "red_border": "#3a1010",
    "orange":     "#D97706", "orange_bg":  "#1a1200", "orange_bdr": "#3a2800",
    "green":      "#7DC242", "green_bg":   "#0f1a0a", "green_bdr":  "#1e2a1a",
}
