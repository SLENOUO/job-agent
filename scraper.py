import requests
import os
import re
import time
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─────────────────────────────────────────────────────────────────
#  FILTRES METIER & CONTRAT
# ─────────────────────────────────────────────────────────────────

# Métiers cibles — Data/IA + Développement Web
METIERS_CIBLES = [
    # Data / IA
    "data engineer", "data analyst", "data scientist", "machine learning",
    "ml engineer", "ai engineer", "big data", "analytics engineer",
    "bi developer", "business intelligence", "data ingenieur", "ingenieur data",
    "apprenti data", "alternance data", "data science", "deep learning",
    "nlp", "computer vision", "llm", "intelligence artificielle",
    "ia generative", "ingenieur ia", "analyste data", "analyste donnees",
    # Dev Web / Software
    "full stack", "fullstack", "backend", "back-end", "frontend", "front-end",
    "web developer", "developpeur web", "software engineer", "python developer",
    "developpeur python", "java developer", "developpeur java", "react developer",
    "developpeur react", "node.js", "nodejs", "developpeur logiciel",
    "ingenieur logiciel", "ingenieur developpement", "devops", "cloud engineer",
    "mlops", "data ops", "flask", "django", "fastapi", "api rest",
]

# Domaines à exclure si aucun métier cible trouvé
DOMAINES_EXCLUS = [
    "marketing", "commercial", "comptabilit", "ressources humaines", " rh ",
    "logistique", "supply chain", "juridique", "droit", "notaire", "avocat",
    "telecom", "reseau", "cybersecurit", "mecanique", "genie civil",
    "batiment", "travaux", "immobilier", "assurance", "banque",
    "chef de projet non technique", "consultant non technique",
    "communication", "journalisme", "redacteur", "graphiste",
    "infirmier", "medecin", "pharmacien", "kinesitherapeute",
    "expert sinistre", "gestionnaire sinistre",
]

# Contrats acceptés
CONTRATS_ACCEPTES = [
    "alternance", "apprentissage", "apprenti", "contrat pro",
    "professionnalisation", "alternant",
]

# Contrats exclus
CONTRATS_EXCLUS = [
    " cdi", " cdd", "stage", "freelance", "interim", "prestataire",
    " vie ", "volontariat", "service civique",
]


def filtrer_offre_metier(offre: dict) -> bool:
    """
    Retourne True si l'offre est dans un domaine Data/IA/Dev.
    Vérifie titre + description en minuscules sans accents.
    """
    import unicodedata
    def normalize(s):
        return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()

    texte = normalize(offre.get("titre", "") + " " + offre.get("description", ""))

    # Au moins un métier cible trouvé → OK
    for metier in METIERS_CIBLES:
        if normalize(metier) in texte:
            return True

    return False


def filtrer_contrat(offre: dict) -> bool:
    """
    Retourne True si l'offre est bien une alternance/apprentissage.
    Vérifie titre + description.
    """
    import unicodedata
    def normalize(s):
        return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()

    texte = normalize(offre.get("titre", "") + " " + offre.get("description", ""))

    # Doit contenir au moins un mot clé alternance
    has_alternance = any(normalize(c) in texte for c in CONTRATS_ACCEPTES)

    # Ne doit pas être uniquement CDI/CDD/Stage
    is_exclu = all(normalize(c) in texte for c in [" cdi"]) and not has_alternance

    return has_alternance and not is_exclu


def extraire_duree(offre: dict) -> int:
    """Extrait la durée en mois depuis le titre ou la description."""
    texte = (offre.get("titre", "") + " " + offre.get("description", "")).lower()
    patterns = [
        r'(\d+)\s*mois',
        r'(\d+)\s*ans?',
    ]
    for pattern in patterns:
        match = re.search(pattern, texte)
        if match:
            val = int(match.group(1))
            if "an" in pattern:
                return val * 12
            return val
    return 0


def filtrer_et_enrichir(offres: list) -> list:
    """
    Applique les filtres métier + contrat sur toutes les offres.
    Ajoute le champ duree_mois.
    Retourne uniquement les offres valides.
    """
    valides = []
    nb_metier = 0
    nb_contrat = 0

    for o in offres:
        if not filtrer_offre_metier(o):
            nb_metier += 1
            continue
        if not filtrer_contrat(o):
            nb_contrat += 1
            continue
        o["duree_mois"] = extraire_duree(o)
        valides.append(o)

    print(f"[Filtre] {nb_metier} offres hors domaine, {nb_contrat} hors contrat alternance.")
    print(f"[Filtre] {len(valides)} offres retenues sur {len(offres)} collectées.")
    return valides


# ─────────────────────────────────────────────────────────────────
#  FRANCE TRAVAIL (API officielle)
# ─────────────────────────────────────────────────────────────────

def get_token() -> str:
    try:
        r = requests.post(FT_AUTH_URL, data={
            "grant_type"   : "client_credentials",
            "client_id"    : CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope"        : "api_offresdemploiv2 o2dsoffre",
        }, timeout=10)
        return r.json().get("access_token", "")
    except Exception as e:
        print(f"[France Travail] Token error: {e}")
        return ""


def scrape_france_travail(keyword: str) -> list:
    offres = []
    try:
        token = get_token()
        if not token:
            return []
        headers = {"Authorization": f"Bearer {token}"}
        params  = {
            "motsCles"     : keyword,
            "natureContrat": "E2",   # E2 = Contrat d'apprentissage
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
                "description"  : item.get("description", "")[:600],
                "email_contact": "",
                "duree_mois"   : 0,
            })
    except Exception as e:
        print(f"[France Travail] {e}")
    return offres


# ─────────────────────────────────────────────────────────────────
#  HELLOWORK (scraping HTML)
# ─────────────────────────────────────────────────────────────────

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
        for card in cards[:20]:
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
                "duree_mois"   : 0,
            })
    except Exception as e:
        print(f"[Hellowork] {e}")
    return offres


# ─────────────────────────────────────────────────────────────────
#  INDEED (scraping HTML)
# ─────────────────────────────────────────────────────────────────

def scrape_indeed(keyword: str) -> list:
    offres = []
    try:
        headers = {
            **HEADERS,
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://fr.indeed.com/",
        }
        url = (
            f"https://fr.indeed.com/emplois"
            f"?q={requests.utils.quote(keyword + ' alternance')}"
            f"&l=France"
            f"&fromage=14"
        )
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.job_seen_beacon")
        for card in cards[:20]:
            titre_el      = card.select_one("h2.jobTitle span[title]") or card.select_one("h2.jobTitle")
            entreprise_el = card.select_one("span[data-testid='company-name']") or card.select_one("span.companyName")
            lieu_el       = card.select_one("div[data-testid='text-location']") or card.select_one("div.companyLocation")
            link_el       = card.select_one("a[data-jk]") or card.select_one("a[href*='/rc/clk']")
            desc_el       = card.select_one("div.job-snippet") or card.select_one("ul.jobCardShelfContainer")
            if not titre_el:
                continue
            titre = titre_el.get("title") or titre_el.get_text(strip=True)
            job_key = link_el.get("data-jk", "") if link_el else ""
            job_url = f"https://fr.indeed.com/voir-emploi?jk={job_key}" if job_key else ""
            if not job_url:
                continue
            offres.append({
                "titre"        : titre,
                "entreprise"   : entreprise_el.get_text(strip=True) if entreprise_el else "N/A",
                "localisation" : lieu_el.get_text(strip=True) if lieu_el else "France",
                "source"       : "Indeed",
                "url"          : job_url,
                "description"  : desc_el.get_text(strip=True) if desc_el else "",
                "email_contact": "",
                "duree_mois"   : 0,
            })
    except Exception as e:
        print(f"[Indeed] {e}")
    return offres


# ─────────────────────────────────────────────────────────────────
#  WELCOME TO THE JUNGLE (scraping HTML)
# ─────────────────────────────────────────────────────────────────

def scrape_wttj(keyword: str) -> list:
    offres = []
    try:
        headers = {**HEADERS, "Referer": "https://www.welcometothejungle.com/"}
        url = (
            f"https://www.welcometothejungle.com/fr/jobs"
            f"?query={requests.utils.quote(keyword)}"
            f"&contract_type[]=apprenticeship"
        )
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        import json as _json, re as _re
        script_tags = soup.find_all("script", type="application/json")
        for script in script_tags:
            try:
                data = _json.loads(script.string or "")
                if isinstance(data, dict):
                    raw = _json.dumps(data)
                    matches = _re.findall(r'"slug"\s*:\s*"([^"]+)".*?"name"\s*:\s*"([^"]+)"', raw)
                    for slug, name in matches[:15]:
                        offres.append({
                            "titre"        : name,
                            "entreprise"   : "N/A",
                            "localisation" : "France",
                            "source"       : "Welcome to the Jungle",
                            "url"          : f"https://www.welcometothejungle.com/fr/companies/{slug}/jobs",
                            "description"  : "",
                            "email_contact": "",
                            "duree_mois"   : 0,
                        })
            except Exception:
                continue
        if not offres:
            cards = soup.select("article[data-testid='job-card']") or soup.select("li[data-testid='search-results-list-item']")
            for card in cards[:15]:
                titre_el      = card.select_one("h3") or card.select_one("h2")
                entreprise_el = card.select_one("span[data-testid='company-name']")
                lieu_el       = card.select_one("span[data-testid='location']")
                link_el       = card.select_one("a[href*='/jobs/']") or card.select_one("a[href]")
                desc_el       = card.select_one("p[class*='description']")
                if not titre_el or not link_el:
                    continue
                href = link_el.get("href", "")
                offres.append({
                    "titre"        : titre_el.get_text(strip=True),
                    "entreprise"   : entreprise_el.get_text(strip=True) if entreprise_el else "N/A",
                    "localisation" : lieu_el.get_text(strip=True) if lieu_el else "France",
                    "source"       : "Welcome to the Jungle",
                    "url"          : f"https://www.welcometothejungle.com{href}" if href.startswith("/") else href,
                    "description"  : desc_el.get_text(strip=True) if desc_el else "",
                    "email_contact": "",
                    "duree_mois"   : 0,
                })
    except Exception as e:
        print(f"[WTTJ] {e}")
    return offres


# ─────────────────────────────────────────────────────────────────
#  APEC (API publique)
# ─────────────────────────────────────────────────────────────────

def scrape_apec(keyword: str) -> list:
    offres = []
    try:
        url = "https://www.apec.fr/cms/webservices/rechercheOffre/results"
        params = {
            "motsCles"   : keyword,
            "typeContrat": "143748",
            "nbResultats": 20,
            "debut"      : 0,
        }
        headers = {
            **HEADERS,
            "Accept"            : "application/json, text/javascript, */*; q=0.01",
            "Referer"           : "https://www.apec.fr/candidat/recherche-emploi.html/emploi",
            "X-Requested-With"  : "XMLHttpRequest",
        }
        r = requests.get(url, headers=headers, params=params, timeout=15)
        data = r.json()
        for item in data.get("resultats", []):
            offre_id   = item.get("id", "")
            titre      = item.get("intitule", "N/A")
            entreprise = item.get("nomEntreprise", "N/A")
            lieu       = item.get("lieuPoste", "France")
            desc       = item.get("texteDescriptionPoste", "") or item.get("accroche", "")
            offres.append({
                "titre"        : titre,
                "entreprise"   : entreprise,
                "localisation" : lieu,
                "source"       : "APEC",
                "url"          : f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/{offre_id}" if offre_id else "",
                "description"  : str(desc)[:600],
                "email_contact": "",
                "duree_mois"   : 0,
            })
    except Exception as e:
        print(f"[APEC] {e}")
    return offres


# ─────────────────────────────────────────────────────────────────
#  ORCHESTRATEUR PRINCIPAL
# ─────────────────────────────────────────────────────────────────

def run_all_scrapers(mots_cles: list = None) -> list:
    """
    1. Scrape les 5 sources
    2. Déduplique par URL
    3. Filtre métier (Data/IA/Dev uniquement)
    4. Filtre contrat (alternance uniquement)
    5. Retourne les offres filtrées
    """
    keywords = mots_cles if mots_cles else SEARCH_KEYWORDS
    all_offres = []
    print(f"[Scraper] Démarrage — {len(keywords)} mots-clés, 5 sources...")

    for kw in keywords:
        print(f"  → France Travail: '{kw}'")
        all_offres += scrape_france_travail(kw)
        time.sleep(0.3)

    for kw in keywords[:8]:
        print(f"  → Hellowork: '{kw}'")
        all_offres += scrape_hellowork(kw)
        time.sleep(0.5)

    for kw in keywords[:6]:
        print(f"  → Indeed: '{kw}'")
        all_offres += scrape_indeed(kw)
        time.sleep(1)

    for kw in keywords[:5]:
        print(f"  → WTTJ: '{kw}'")
        all_offres += scrape_wttj(kw)
        time.sleep(0.8)

    for kw in keywords[:6]:
        print(f"  → APEC: '{kw}'")
        all_offres += scrape_apec(kw)
        time.sleep(0.5)

    # Déduplication par URL
    seen, unique = set(), []
    for o in all_offres:
        if o["url"] and o["url"] not in seen:
            seen.add(o["url"])
            unique.append(o)

    print(f"[Scraper] {len(unique)} offres uniques avant filtrage.")

    # Filtrage métier + contrat
    filtrees = filtrer_et_enrichir(unique)

    return filtrees