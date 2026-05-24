import os
from dotenv import load_dotenv
load_dotenv()

# === API ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# === EMAIL ===
EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587

# === SCORING ===
MIN_SCORE_AUTO_APPLY = 7   # ← baissé de 8 à 7, sinon trop peu de lettres générées
MIN_SCORE_DISPLAY    = 5

# === SCRAPING — fallback uniquement si cv_parser échoue ===
SEARCH_KEYWORDS = [
    "alternance informatique",
    "alternance ingénieur",
    "alternance développeur",
    "alternance data",
    "alternance finance",
    "alternance marketing digital",
    "alternance ressources humaines",
    "alternance comptabilité",
    "alternance commerce",
    "alternance communication",
]

LOCATIONS = ["Paris", "Île-de-France", "France"]

# BLACKLIST — uniquement mots EXACTS et non ambigus
# "lead", "manager" supprimés car trop présents dans descriptions normales
BLACKLIST_KEYWORDS = [
    "10 ans d'expérience",
    "8 ans d'expérience",
    "15 ans",
    "directeur",
    "chef de projet senior",
    "cdi senior",
]

# === PATHS ===
DB_PATH        = "data/agent.db"
UPLOADS_FOLDER = "uploads"