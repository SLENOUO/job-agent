import os
from dotenv import load_dotenv
load_dotenv()

# === API ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# === EMAIL (Gmail App Password) ===
EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587

# === SCORING ===
MIN_SCORE_AUTO_APPLY = 8
MIN_SCORE_DISPLAY    = 6

# === SCRAPING ===
SEARCH_KEYWORDS = [
    "alternance data engineer",
    "alternance data scientist",
    "alternance big data",
    "apprenti ingénieur data",
    "alternance data analyst",
]
LOCATIONS = ["Paris", "Île-de-France", "France"]

BLACKLIST_KEYWORDS = ["senior", "10 ans", "8 ans", "confirmé", "lead", "manager", "directeur"]

# === PATHS ===
DB_PATH        = "data/agent.db"
UPLOADS_FOLDER = "uploads"