"""
agent.py
Cœur de l'agent :
  1. Score chaque offre par rapport au CV (pondération 40/25/15/15/5)
  2. Bonus durée alternance (+2 pour 24 mois, +1 pour 18 mois, +0.5 pour 12 mois)
  3. Génère une lettre de motivation personnalisée
  4. Retourne les 20 meilleures offres uniquement
"""
import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MIN_SCORE_AUTO_APPLY, BLACKLIST_KEYWORDS

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────────────────────────
#  STACK CIBLE — pour le scoring
# ─────────────────────────────────────────────────────────────────
STACK_CIBLE = [
    "python", "sql", "flask", "api rest", "ia generative", "machine learning",
    "data science", "big data", "java", "react", "javascript", "typescript",
    "developpement web", "cloud", "docker", "spark", "hadoop", "airflow",
    "dbt", "power bi", "tableau", "scikit", "tensorflow", "pytorch",
    "fastapi", "django", "node", "git", "mlops", "llm", "nlp",
]

# ─────────────────────────────────────────────────────────────────
#  BLACKLIST — vérifie uniquement sur le titre
# ─────────────────────────────────────────────────────────────────
def is_blacklisted(offre: dict) -> tuple:
    titre_lower = offre.get("titre", "").lower()
    for mot in BLACKLIST_KEYWORDS:
        if mot.lower() in titre_lower:
            return True, mot
    return False, ""


# ─────────────────────────────────────────────────────────────────
#  BONUS DUREE ALTERNANCE
# ─────────────────────────────────────────────────────────────────
def bonus_duree(duree_mois: int) -> float:
    if duree_mois >= 24:
        return 2.0
    if duree_mois >= 18:
        return 1.0
    if duree_mois >= 12:
        return 0.5
    return 0.0


# ─────────────────────────────────────────────────────────────────
#  SCORING : Offre ↔ Profil CV (pondéré 40/25/15/15/5)
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
    poste_cherche = profil.get("poste_recherche", "alternance data")
    niveau        = profil.get("niveau_etudes", "Bac+3")
    type_contrat  = profil.get("type_contrat", "Alternance")
    duree_mois    = offre.get("duree_mois", 0)
    bonus         = bonus_duree(duree_mois)

    prompt = f"""
Tu es un expert RH spécialisé en recrutement tech/data.

PROFIL CANDIDAT :
- Poste recherché : {poste_cherche}
- Type de contrat : {type_contrat}
- Niveau : {niveau} à {profil.get('ecole', '')}
- Spécialisation : {profil.get('specialisation', '')}
- Stack technique : {stack_str}
- Expériences : {experiences[:800]}
- Disponibilité : {profil.get('disponibilite', 'Non précisée')}
- Projet phare : Job Agent SaaS (Flask, Claude API, Stripe, Railway, scraping multi-sources)

OFFRE À ANALYSER :
- Titre : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Localisation : {offre.get('localisation', '')}
- Durée : {duree_mois} mois
- Description : {offre.get('description', '')[:800]}

GRILLE DE SCORING PONDÉRÉE :

1. Correspondance métier (40%) — Le poste correspond-il exactement au domaine data/IA/dev du candidat ?
   - 10/10 : data engineer, data scientist, ML engineer, full stack, backend Python → score partiel 9-10
   - 7-8/10 : analytics, BI, data analyst, frontend, web developer
   - 4-6/10 : IT généraliste, support technique avec data
   - 1-3/10 : hors domaine

2. Stack technique (25%) — Les technologies demandées matchent-elles la stack du candidat ?
   Stack cible : Python, SQL, Flask, APIs REST, IA générative, ML, Big Data, Java, React, Cloud
   - Fort match (8-10) : 3+ techs communes
   - Moyen (5-7) : 1-2 techs communes
   - Faible (1-4) : aucune tech commune

3. Niveau d'études (15%) — L'offre correspond-elle au niveau Bac+3/4/5 du candidat ?
   - 10 : niveau explicitement Bac+3 à Bac+5
   - 7 : niveau non précisé ou "selon profil"
   - 3 : BTS/Bac+2 uniquement ou niveau trop élevé (Bac+6+)

4. Durée alternance (15%) — Durée détectée : {duree_mois} mois
   - 24 mois → score partiel 10
   - 18 mois → score partiel 8
   - 12 mois → score partiel 6
   - Non précisée → score partiel 5

5. Localisation (5%) — Proximité Paris/Île-de-France ou télétravail
   - Paris/IDF ou remote : 10
   - Autre grande ville : 6
   - Province éloignée : 3

Calcule le score final pondéré entre 0 et 10.

Retourne UNIQUEMENT ce JSON valide (sans markdown, sans commentaire) :
{{
  "score": <entier 0-10>,
  "resume_ia": "<2 phrases : ce que propose l'offre + pourquoi ça matche ou pas>",
  "match_stack": "<techs du candidat qui correspondent, séparées par virgules>",
  "points_forts": "<ce qui joue en faveur du candidat>",
  "points_faibles": "<ce qui manque>",
  "mode_candidature": "email" ou "formulaire",
  "email_contact": "<email si détecté, sinon vide>"
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
        result = json.loads(text)

        # Applique le bonus durée au score final
        if bonus > 0 and duree_mois > 0:
            score_brut = result.get("score", 0)
            score_final = min(10, round(score_brut + bonus))
            result["score"] = score_final
            if bonus >= 1:
                result["points_forts"] = f"[+{bonus}pts durée {duree_mois}mois] " + result.get("points_forts", "")

        return result
    except Exception as e:
        print(f"  [Score] Erreur: {e}")
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
    prompt = f"""
Tu es expert en candidatures tech/data en France. Rédige une lettre de motivation en français.

RÈGLES STRICTES :
- Aucun markdown : pas de **, pas de *, pas de #, pas de ---
- Ne mets PAS l'objet dans le corps
- Ne mets PAS le nom du candidat en haut (ajouté automatiquement)
- Commence directement par "Madame, Monsieur,"
- 3 paragraphes uniquement :
  * §1 (2-3 lignes) : accroche spécifique à l'entreprise et au poste
  * §2 (4-5 lignes) : compétences qui matchent avec exemples concrets — mentionne le projet Job Agent SaaS si pertinent
  * §3 (2-3 lignes) : disponibilité + appel à l'action
- Termine par : "Dans l'attente de votre retour, je reste disponible pour un entretien."
- Signe avec : {profil.get('nom', '')}
- Texte brut uniquement

PROFIL :
- Nom : {profil.get('nom', '')}
- Formation : {profil.get('niveau_etudes', '')} à {profil.get('ecole', '')}
- Spécialisation : {profil.get('specialisation', '')}
- Poste recherché : {profil.get('poste_recherche', '')}
- Stack : {', '.join(profil.get('competences_techniques', [])[:10])}
- Expériences : {json.dumps(profil.get('experiences', [])[:2], ensure_ascii=False)}
- Projets : {json.dumps(profil.get('projets', [])[:2], ensure_ascii=False)}
- Disponibilité : {profil.get('disponibilite', 'Non précisée')}
- Pitch : {profil.get('pitch', '')}

OFFRE :
- Poste : {offre.get('titre', '')}
- Entreprise : {offre.get('entreprise', '')}
- Localisation : {offre.get('localisation', '')}
- Durée : {offre.get('duree_mois', 0)} mois
- Description : {offre.get('description', '')[:600]}

POINTS FORTS identifiés : {scoring.get('points_forts', '')}
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
      1. Score pondéré vs profil CV (40/25/15/15/5) + bonus durée
      2. Si score >= MIN_SCORE_AUTO_APPLY → génère lettre de motivation
    Retourne les 20 meilleures offres triées par score décroissant.
    """
    nom_candidat = profil.get('nom', 'le candidat')
    print(f"\n[Agent] Analyse de {len(offres)} offres filtrées pour {nom_candidat}...")
    resultats = []

    for i, offre in enumerate(offres):
        titre      = offre.get('titre', 'N/A')
        entreprise = offre.get('entreprise', 'N/A')
        duree      = offre.get('duree_mois', 0)
        print(f"  [{i+1}/{len(offres)}] {titre} — {entreprise} ({duree}mois)")

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
            "statut"           : "pret" if score >= MIN_SCORE_AUTO_APPLY else "ignore",
        })

    # Tri par score décroissant
    resultats.sort(key=lambda x: x["score"], reverse=True)

    # Retourne uniquement les 20 meilleures
    top20 = resultats[:20]

    nb_pret   = sum(1 for r in top20 if r["statut"] == "pret")
    nb_ignore = len(top20) - nb_pret
    print(f"\n[Agent] Top 20 — {nb_pret} candidature(s) prêtes, {nb_ignore} ignorées.")
    return top20