"""
agent.py
Cœur de l'agent :
  1. Score chaque offre par rapport au CV de l'utilisateur
  2. Génère une lettre de motivation personnalisée et propre
"""
import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MIN_SCORE_AUTO_APPLY, BLACKLIST_KEYWORDS

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────────────────────────
#  SCORING : Offre ↔ Profil CV
# ─────────────────────────────────────────────────────────────────
def scorer_offre(offre: dict, profil: dict) -> dict:
    titre_lower = (offre.get("titre", "") + " " + offre.get("description", "")).lower()
    for mot in BLACKLIST_KEYWORDS:
        if mot in titre_lower:
            return {
                "score": 1,
                "resume_ia": f"Offre blacklistée (mot-clé: {mot})",
                "match_stack": "",
                "points_forts": "",
                "points_faibles": "",
                "mode_candidature": "formulaire",
                "email_contact": "",
            }

    stack_str     = ", ".join(profil.get("competences_techniques", []))
    experiences   = json.dumps(profil.get("experiences", []), ensure_ascii=False)
    poste_cherche = profil.get("poste_recherche", "alternance data")
    niveau        = profil.get("niveau_etudes", "Bac+3")

    prompt = f"""
Voici le profil d'un candidat extrait de son CV :
- Poste recherché : {poste_cherche}
- Niveau : {niveau} à {profil.get('ecole', '')}
- Stack technique : {stack_str}
- Expériences : {experiences[:600]}
- Disponibilité : {profil.get('disponibilite', 'Septembre 2026')}

Voici une offre d'alternance :
- Titre : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Localisation : {offre.get('localisation', '')}
- Description : {offre.get('description', '')[:600]}

Analyse le matching et retourne UNIQUEMENT ce JSON (sans markdown) :
{{
  "score": <0-10>,
  "resume_ia": "<2 phrases : ce que propose l'offre + pourquoi ça matche ou pas>",
  "match_stack": "<compétences du candidat qui correspondent>",
  "points_forts": "<ce qui joue en faveur du candidat>",
  "points_faibles": "<ce qui manque ou pose problème>",
  "mode_candidature": "email" ou "formulaire",
  "email_contact": "<email si détecté, sinon vide>"
}}

Scoring :
10 = match parfait
7-9 = bon match
4-6 = match partiel
1-3 = mauvais match
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"  [Score] Erreur: {e}")
        return {
            "score": 0, "resume_ia": "", "match_stack": "",
            "points_forts": "", "points_faibles": "",
            "mode_candidature": "formulaire", "email_contact": ""
        }


# ─────────────────────────────────────────────────────────────────
#  NETTOYAGE LETTRE
# ─────────────────────────────────────────────────────────────────
def nettoyer_lettre(texte: str) -> str:
    """Supprime tout le markdown et les éléments parasites de la lettre."""
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)           # **gras** → gras
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)               # *italique* → italique
    texte = re.sub(r'^#{1,6}\s*.*?\n', '', texte, flags=re.MULTILINE)  # # Titres
    texte = re.sub(r'-{2,}', '', texte)                      # --- séparateurs
    texte = re.sub(r'^Objet\s*:.*?\n', '', texte, flags=re.MULTILINE)  # Objet dans le corps
    texte = re.sub(r'Lettre de motivation\s*\n?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\n{3,}', '\n\n', texte)                 # Espaces multiples
    return texte.strip()


# ─────────────────────────────────────────────────────────────────
#  GÉNÉRATION LETTRE DE MOTIVATION
# ─────────────────────────────────────────────────────────────────
def generer_lettre(offre: dict, profil: dict, scoring: dict) -> str:
    """
    Génère une lettre de motivation propre, sans markdown, sans objet dans le corps.
    L'objet est géré séparément dans le PDF.
    """
    prompt = f"""
Tu es expert en candidatures data/tech. Rédige une lettre de motivation en français.

RÈGLES STRICTES :
- Ne mets AUCUN markdown : pas de **, pas de *, pas de #, pas de ---
- Ne mets PAS l'objet dans le corps de la lettre
- Ne mets PAS le nom du candidat en haut (il sera ajouté automatiquement)
- Commence directement par "Madame, Monsieur,"
- 3 paragraphes uniquement
- Paragraphe 1 : ouverture spécifique à l'entreprise et au poste (2-3 lignes)
- Paragraphe 2 : compétences techniques qui matchent avec chiffres/résultats (4-5 lignes)
- Paragraphe 3 : disponibilité + appel à l'action (2-3 lignes)
- Termine par : "Dans l'attente de votre retour, je reste disponible pour un entretien."
- Signature : {profil.get('nom', '')}
- Texte brut uniquement, aucune mise en forme

PROFIL CANDIDAT :
- Nom : {profil.get('nom', '')}
- Formation : {profil.get('niveau_etudes', '')} à {profil.get('ecole', '')}
- Spécialisation : {profil.get('specialisation', '')}
- Stack : {', '.join(profil.get('competences_techniques', [])[:8])}
- Expériences : {json.dumps(profil.get('experiences', [])[:2], ensure_ascii=False)}
- Projets : {json.dumps(profil.get('projets', [])[:2], ensure_ascii=False)}
- Disponibilité : {profil.get('disponibilite', 'Septembre 2026')}

OFFRE CIBLÉE :
- Poste : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Localisation : {offre.get('localisation', '')}
- Description : {offre.get('description', '')[:500]}

POINTS FORTS pour cette offre : {scoring.get('points_forts', '')}
STACK MATCHÉE : {scoring.get('match_stack', '')}
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        lettre = response.content[0].text.strip()
        return nettoyer_lettre(lettre)
    except Exception as e:
        print(f"  [LM] Erreur: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────
#  PIPELINE COMPLET
# ─────────────────────────────────────────────────────────────────
def run_agent_pipeline(offres: list, profil: dict) -> list:
    """
    Pour chaque offre :
      1. Score vs profil CV
      2. Si score >= MIN_SCORE_AUTO_APPLY → génère lettre de motivation
    Retourne liste enrichie triée par score décroissant.
    """
    print(f"\n[Agent] Analyse de {len(offres)} offres pour {profil.get('nom', 'le candidat')}...")
    resultats = []

    for i, offre in enumerate(offres):
        print(f"  [{i+1}/{len(offres)}] {offre.get('titre', '')} — {offre.get('entreprise', '')}")

        scoring = scorer_offre(offre, profil)
        score   = scoring.get("score", 0)

        lettre = ""
        if score >= MIN_SCORE_AUTO_APPLY:
            print(f"    ✅ Score {score}/10 — Génération lettre...")
            lettre = generer_lettre(offre, profil, scoring)

        resultats.append({
            **offre,
            "score"            : score,
            "resume_ia"        : scoring.get("resume_ia", ""),
            "match_stack"      : scoring.get("match_stack", ""),
            "points_forts"     : scoring.get("points_forts", ""),
            "points_faibles"   : scoring.get("points_faibles", ""),
            "mode_candidature" : scoring.get("mode_candidature", "formulaire"),
            "email_contact"    : scoring.get("email_contact", ""),
            "lettre_motivation": lettre,
            "statut"           : "prêt" if score >= MIN_SCORE_AUTO_APPLY else "ignoré",
        })

    resultats.sort(key=lambda x: x["score"], reverse=True)
    nb_pret = sum(1 for r in resultats if r["statut"] == "prêt")
    print(f"\n[Agent] Terminé — {nb_pret} candidature(s) prêtes sur {len(resultats)} offres.")
    return resultats