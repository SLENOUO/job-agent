import requests
import os
from dotenv import load_dotenv
from config import SEARCH_KEYWORDS

load_dotenv()

FT_AUTH_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_API_URL  = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

CLIENT_ID     = os.getenv("FT_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET", "")


def get_token() -> str:
    r = requests.post(FT_AUTH_URL, data={
        "grant_type"   : "client_credentials",
        "client_id"    : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope"        : "api_offresdemploiv2 o2dsoffre",
    })
    return r.json().get("access_token", "")


def scrape_france_travail(keyword: str) -> list:
    offres = []
    try:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}
        params  = {
            "motsCles"     : keyword,
            "natureContrat": "E2",
            "range"        : "0-14",
        }
        r = requests.get(FT_API_URL, headers=headers, params=params, timeout=15)
        for item in r.json().get("resultats", []):
            offres.append({
                "titre"        : item.get("intitule", "N/A"),
                "entreprise"   : item.get("entreprise", {}).get("nom", "N/A"),
                "localisation" : item.get("lieuTravail", {}).get("libelle", "N/A"),
                "source"       : "France Travail",
                "url"          : item.get("origineOffre", {}).get("urlOrigine", ""),
                "description"  : item.get("description", "")[:500],
                "email_contact": "",
            })
    except Exception as e:
        print(f"[France Travail] {e}")
    return offres


def run_all_scrapers() -> list:
    all_offres = []
    print("[Scraper] Démarrage France Travail API...")
    for kw in SEARCH_KEYWORDS:
        print(f"  → '{kw}'")
        all_offres += scrape_france_travail(kw)

    seen, unique = set(), []
    for o in all_offres:
        if o["url"] and o["url"] not in seen:
            seen.add(o["url"])
            unique.append(o)

    print(f"[Scraper] {len(unique)} offres uniques collectées.")
    return unique