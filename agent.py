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
#  BLACKLIST — vérifie uniquement sur le titre (pas la description)
# ─────────────────────────────────────────────────────────────────
def is_blacklisted(offre: dict) -> tuple[bool, str]:
    """
    Retourne (True, mot_trouvé) si l'offre est blacklistée, (False, "") sinon.
    On ne vérifie QUE le titre pour éviter les faux positifs sur les descriptions.
    """
    titre_lower = offre.get("titre", "").lower()
    for mot in BLACKLIST_KEYWORDS:
        if mot.lower() in titre_lower:
            return True, mot
    return False, ""
 
 
# ─────────────────────────────────────────────────────────────────
#  SCORING : Offre ↔ Profil CV
# ─────────────────────────────────────────────────────────────────
def scorer_offre(offre: dict, profil: dict) -> dict:
    blacklisted, mot = is_blacklisted(offre)
    if blacklisted:
        return {
            "score"           : 1,
            "resume_ia"       : f"Offre blacklistée (mot-clé: {mot})",
            "match_stack"     : "",
            "points_forts"    : "",
            "points_faibles"  : "",
            "mode_candidature": "formulaire",
            "email_contact"   : "",
        }
 
    stack_str     = ", ".join(profil.get("competences_techniques", []))
    experiences   = json.dumps(profil.get("experiences", []), ensure_ascii=False)
    poste_cherche = profil.get("poste_recherche", "alternance")
    niveau        = profil.get("niveau_etudes", "Bac+3")
    type_contrat  = profil.get("type_contrat", "Alternance")
 
    prompt = f"""
Tu es un expert RH spécialisé dans le matching candidat/offre.
 
Profil du candidat :
- Poste recherché : {poste_cherche}
- Type de contrat : {type_contrat}
- Niveau : {niveau} à {profil.get('ecole', '')}
- Spécialisation : {profil.get('specialisation', '')}
- Stack technique : {stack_str}
- Expériences : {experiences[:800]}
- Disponibilité : {profil.get('disponibilite', 'Non précisée')}
 
Offre à analyser :
- Titre : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Localisation : {offre.get('localisation', '')}
- Description : {offre.get('description', '')[:800]}
 
INSTRUCTIONS DE SCORING :
- Score 9-10 : match quasi parfait (poste, stack, niveau, contrat tous alignés)
- Score 7-8  : bon match avec quelques écarts mineurs
- Score 5-6  : match partiel, candidat peut postuler mais profil incomplet
- Score 3-4  : peu de correspondance, domaine différent ou niveau inadapté
- Score 1-2  : aucun lien avec le profil du candidat
 
Retourne UNIQUEMENT ce JSON valide (sans markdown, sans commentaire) :
{{
  "score": <entier 1-10>,
  "resume_ia": "<2 phrases : ce que propose l'offre + pourquoi ça matche ou pas>",
  "match_stack": "<compétences du candidat qui correspondent à l'offre, séparées par virgules>",
  "points_forts": "<ce qui joue en faveur du candidat pour cette offre>",
  "points_faibles": "<ce qui manque ou pourrait poser problème>",
  "mode_candidature": "email" ou "formulaire",
  "email_contact": "<email si détecté dans la description, sinon chaîne vide>"
}}
"""
 
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"  [Score] Erreur parsing JSON: {e}")
        return {
            "score"           : 0,
            "resume_ia"       : "",
            "match_stack"     : "",
            "points_forts"    : "",
            "points_faibles"  : "",
            "mode_candidature": "formulaire",
            "email_contact"   : "",
        }
 
 
# ─────────────────────────────────────────────────────────────────
#  NETTOYAGE LETTRE
# ─────────────────────────────────────────────────────────────────
def nettoyer_lettre(texte: str) -> str:
    """Supprime tout le markdown et les éléments parasites de la lettre."""
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^#{1,6}\s*.*?\n', '', texte, flags=re.MULTILINE)
    texte = re.sub(r'-{2,}', '', texte)
    texte = re.sub(r'^Objet\s*:.*?\n', '', texte, flags=re.MULTILINE)
    texte = re.sub(r'Lettre de motivation\s*\n?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\n{3,}', '\n\n', texte)
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
Tu es expert en candidatures. Rédige une lettre de motivation en français, adaptée au domaine : {profil.get('specialisation', profil.get('poste_recherche', ''))}.
 
RÈGLES STRICTES :
- Aucun markdown : pas de **, pas de *, pas de #, pas de ---
- Ne mets PAS l'objet dans le corps
- Ne mets PAS le nom du candidat en haut (ajouté automatiquement)
- Commence directement par "Madame, Monsieur,"
- 3 paragraphes uniquement :
  * Paragraphe 1 (2-3 lignes) : accroche spécifique à l'entreprise et au poste
  * Paragraphe 2 (4-5 lignes) : compétences qui matchent avec exemples concrets/chiffres si possible
  * Paragraphe 3 (2-3 lignes) : disponibilité + appel à l'action
- Termine par : "Dans l'attente de votre retour, je reste disponible pour un entretien."
- Puis signe avec : {profil.get('nom', '')}
- Texte brut uniquement
 
PROFIL CANDIDAT :
- Nom : {profil.get('nom', '')}
- Formation : {profil.get('niveau_etudes', '')} à {profil.get('ecole', '')}
- Spécialisation : {profil.get('specialisation', '')}
- Poste recherché : {profil.get('poste_recherche', '')}
- Stack : {', '.join(profil.get('competences_techniques', [])[:10])}
- Expériences : {json.dumps(profil.get('experiences', [])[:2], ensure_ascii=False)}
- Projets : {json.dumps(profil.get('projets', [])[:2], ensure_ascii=False)}
- Disponibilité : {profil.get('disponibilite', 'Non précisée')}
- Pitch : {profil.get('pitch', '')}
 
OFFRE CIBLÉE :
- Poste : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Localisation : {offre.get('localisation', '')}
- Description : {offre.get('description', '')[:600]}
 
POINTS FORTS identifiés pour cette offre : {scoring.get('points_forts', '')}
STACK MATCHÉE : {scoring.get('match_stack', '')}
"""
 
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
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
    nom_candidat = profil.get('nom', 'le candidat')
    print(f"\n[Agent] Analyse de {len(offres)} offres pour {nom_candidat}...")
    resultats = []
 
    for i, offre in enumerate(offres):
        titre     = offre.get('titre', 'N/A')
        entreprise = offre.get('entreprise', 'N/A')
        print(f"  [{i+1}/{len(offres)}] {titre} — {entreprise}")
 
        scoring = scorer_offre(offre, profil)
        score   = scoring.get("score", 0)
 
        lettre = ""
        if score >= MIN_SCORE_AUTO_APPLY:
            print(f"    ✅ Score {score}/10 — Génération lettre...")
            lettre = generer_lettre(offre, profil, scoring)
        else:
            print(f"    ⏭️  Score {score}/10 — ignoré")
 
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
    nb_ignore = len(resultats) - nb_pret
    print(f"\n[Agent] Terminé — {nb_pret} candidature(s) prêtes, {nb_ignore} ignorées sur {len(resultats)} offres.")
    return resultats