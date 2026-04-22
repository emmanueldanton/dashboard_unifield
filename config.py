from __future__ import annotations
from zoneinfo import ZoneInfo

API_BASE                  = "https://api.cad42.com"
BATTERY_WARNING_THRESHOLD = 3.5
ENDING_SOON_DAYS          = 30
PAST_DAYS                 = 10
MAX_WORKERS               = 10

PARASITE_KEYWORDS = {"atelier", "stock", "test", "dev"}

PARIS_TZ = ZoneInfo("Europe/Paris")

C = {
    "accent":     "#5D9050", "accent_bg":  "#F0F5EF",
    "bg":         "#F8FAFB", "surface":    "#FFFFFF", "border":    "#E2E8F0",
    "text":       "#1E293B", "text_muted": "#64748B", "text_light":"#94A3B8",
    "red":        "#DC2626", "red_bg":     "#FEF2F2", "red_border":"#FECACA",
    "orange":     "#D97706", "orange_bg":  "#FFFBEB", "orange_bdr":"#FDE68A",
    "green":      "#16A34A", "green_bg":   "#F0FDF4", "green_bdr": "#BBF7D0",
}
