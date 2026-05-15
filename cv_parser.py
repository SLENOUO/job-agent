import json
import anthropic
import pdfplumber
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"[CV Parser] Erreur extraction PDF: {e}")
    return text.strip()


def parse_cv(pdf_path: str) -> dict:
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        return {"error": "Impossible d'extraire le texte du CV."}

    prompt = f"""
Tu es un expert RH et recrutement tech. Analyse ce CV et retourne UNIQUEMENT un JSON valide (sans markdown) avec cette structure exacte :

{{
  "nom": "Prénom Nom",
  "email": "email@example.com",
  "telephone": "+33...",
  "niveau_etudes": "Bac+3 / Bac+5 / etc.",
  "ecole": "Nom de l'école",
  "specialisation": "Spécialisation principale",
  "poste_recherche": "Intitulé du poste recherché",
  "type_contrat": "Alternance / Stage / CDI",
  "disponibilite": "Septembre 2026 / Immédiat / etc.",
  "competences_techniques": ["Python", "SQL", "Spark", "..."],
  "competences_soft": ["Travail en équipe", "Rigueur", "..."],
  "langues": ["Français (natif)", "Anglais (B2)", "..."],
  "experiences": [
    {{
      "entreprise": "Nom entreprise",
      "poste": "Intitulé poste",
      "duree": "6 mois",
      "description": "Ce qu'il a fait en 1-2 phrases"
    }}
  ],
  "projets": [
    {{
      "nom": "Nom projet",
      "technologies": ["Python", "Pandas"],
      "description": "Description courte"
    }}
  ],
  "pitch": "Résumé du profil en 3 phrases max pour une lettre de motivation"
}}

CV à analyser :
---
{raw_text[:4000]}
---
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        profil = json.loads(text)
        profil["cv_raw"] = raw_text[:3000]
        return profil
    except Exception as e:
        print(f"[CV Parser] Erreur Claude: {e}")
        return {"error": str(e), "cv_raw": raw_text[:3000]}