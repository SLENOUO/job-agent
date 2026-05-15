import json
import anthropic
from config import ANTHROPIC_API_KEY, MIN_SCORE_AUTO_APPLY, BLACKLIST_KEYWORDS

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


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
        return {"score": 0, "resume_ia": "", "match_stack": "", "points_forts": "", "points_faibles": "", "mode_candidature": "formulaire", "email_contact": ""}


def generer_lettre(offre: dict, profil: dict, scoring: dict) -> str:
    prompt = f"""
Rédige une lettre de motivation courte en français.

FORMAT :
- 3 paragraphes sans titre
- Paragraphe 1 : ouverture spécifique à l'entreprise et au poste
- Paragraphe 2 : compétences techniques qui matchent avec chiffres/résultats
- Paragraphe 3 : disponibilité + appel à l'action
- Fermeture : "Dans l'attente de votre retour, je reste disponible pour un entretien."
- Signature : {profil.get('nom', '')}

PROFIL :
- Nom : {profil.get('nom', '')}
- Formation : {profil.get('niveau_etudes', '')} à {profil.get('ecole', '')}
- Stack : {', '.join(profil.get('competences_techniques', [])[:8])}
- Expériences : {json.dumps(profil.get('experiences', [])[:2], ensure_ascii=False)}
- Disponibilité : {profil.get('disponibilite', 'Septembre 2026')}

OFFRE :
- Poste : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Description : {offre.get('description', '')[:500]}

POINTS FORTS : {scoring.get('points_forts', '')}
"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  [LM] Erreur: {e}")
        return ""


def run_agent_pipeline(offres: list, profil: dict) -> list:
    print(f"\n[Agent] Analyse de {len(offres)} offres...")
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
            "score"           : score,
            "resume_ia"       : scoring.get("resume_ia", ""),
            "match_stack"     : scoring.get("match_stack", ""),
            "points_forts"    : scoring.get("points_forts", ""),
            "points_faibles"  : scoring.get("points_faibles", ""),
            "mode_candidature": scoring.get("mode_candidature", "formulaire"),
            "email_contact"   : scoring.get("email_contact", ""),
            "lettre_motivation": lettre,
            "statut"          : "prêt" if score >= MIN_SCORE_AUTO_APPLY else "ignoré",
        })

    resultats.sort(key=lambda x: x["score"], reverse=True)
    nb_pret = sum(1 for r in resultats if r["statut"] == "prêt")
    print(f"\n[Agent] Terminé — {nb_pret} candidature(s) prêtes.")
    return resultats