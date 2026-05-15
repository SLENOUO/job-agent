# 🤖 JobAgent — Agent IA de candidature automatique

Agent intelligent qui scrape les offres d'alternance Data, les analyse avec Claude (Anthropic), génère des lettres de motivation personnalisées et postule automatiquement.

## Fonctionnalités

- 📄 Extraction automatique du profil depuis un CV PDF
- 🔍 Scraping des offres sur France Travail API
- 🧠 Scoring IA offre ↔ CV (0-10) via Claude
- ✉️ Génération de lettres de motivation personnalisées
- 🚀 Candidature semi-automatique (email ou ouverture formulaire)
- 📊 Dashboard web pour suivre les candidatures

## Stack technique

- Python, Flask, SQLite
- Anthropic Claude API (Haiku + Sonnet)
- France Travail API
- pdfplumber, requests, BeautifulSoup

## Installation

```bash
git clone https://github.com/SLENOUO/job-agent
cd job-agent
pip install flask anthropic pdfplumber python-dotenv requests beautifulsoup4
```

Crée un fichier `.env` :
## Lancement

```bash
python app.py
```

Puis ouvre http://localhost:5000

## Auteur

Stéphan LENOUO — Étudiant ingénieur Data @ ESIGELEC