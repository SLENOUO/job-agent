import requests
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from config import SEARCH_KEYWORDS

load_dotenv()

FT_AUTH_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_API_URL  = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

CLIENT_ID     = os.getenv("FT_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


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
            "range"        : "0-99",
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


def scrape_hellowork(keyword: str) -> list:
    offres = []
    try:
        url = (
            f"https://www.hellowork.com/fr-fr/emploi/recherche.html"
            f"?k={requests.utils.quote(keyword)}"
            f"&c=Alternance"
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("li[data-id-offre]")
        for card in cards[:15]:
            titre_el      = card.select_one("h3")
            entreprise_el = card.select_one("span[data-cy='company-name']")
            lieu_el       = card.select_one("span[data-cy='localization']")
            link_el       = card.select_one("a[href]")
            desc_el       = card.select_one("p[data-cy='description']")
            if not titre_el or not link_el:
                continue
            href = link_el.get("href", "")
            offres.append({
                "titre"        : titre_el.get_text(strip=True),
                "entreprise"   : entreprise_el.get_text(strip=True) if entreprise_el else "N/A",
                "localisation" : lieu_el.get_text(strip=True) if lieu_el else "France",
                "source"       : "Hellowork",
                "url"          : f"https://www.hellowork.com{href}" if href.startswith("/") else href,
                "description"  : desc_el.get_text(strip=True) if desc_el else "",
                "email_contact": "",
            })
    except Exception as e:
        print(f"[Hellowork] {e}")
    return offres


def run_all_scrapers(mots_cles: list = None) -> list:
    """
    mots_cles : liste extraite du profil CV du client.
    Si None, utilise les mots-clés par défaut du config.
    """
    keywords = mots_cles if mots_cles else SEARCH_KEYWORDS
    all_offres = []
    print(f"[Scraper] Démarrage — {len(keywords)} mots-clés...")

    for kw in keywords:
        print(f"  → France Travail: '{kw}'")
        all_offres += scrape_france_travail(kw)

    for kw in keywords[:8]:
        print(f"  → Hellowork: '{kw}'")
        all_offres += scrape_hellowork(kw)

    # Déduplication par URL
    seen, unique = set(), []
    for o in all_offres:
        if o["url"] and o["url"] not in seen:
            seen.add(o["url"])
            unique.append(o)

    print(f"[Scraper] {len(unique)} offres uniques collectées.")
    return unique