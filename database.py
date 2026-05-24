import os, json
import psycopg2
import psycopg2.extras
from psycopg2 import errors as pg_errors
 
DATABASE_URL = os.getenv("DATABASE_URL", "")
 
 
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    return conn
 
 
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            nom         TEXT,
            role        TEXT DEFAULT 'client',
            actif       INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
 
        CREATE TABLE IF NOT EXISTS profils (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER,
            nom         TEXT,
            email       TEXT,
            cv_path     TEXT,
            profil_json TEXT,
            created_at  TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'))
        );
 
        CREATE TABLE IF NOT EXISTS offres (
            id                SERIAL PRIMARY KEY,
            profil_id         INTEGER,
            user_id           INTEGER,
            titre             TEXT,
            entreprise        TEXT,
            localisation      TEXT,
            source            TEXT,
            url               TEXT,
            description       TEXT,
            score             INTEGER DEFAULT 0,
            resume_ia         TEXT,
            match_stack       TEXT,
            points_forts      TEXT,
            points_faibles    TEXT,
            mode_candidature  TEXT DEFAULT 'formulaire',
            email_contact     TEXT,
            lettre_motivation TEXT,
            statut            TEXT DEFAULT 'ignoré',
            date_analyse      TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            UNIQUE(user_id, url)
        );
 
        CREATE TABLE IF NOT EXISTS candidatures (
            id          SERIAL PRIMARY KEY,
            offre_id    INTEGER,
            profil_id   INTEGER,
            user_id     INTEGER,
            mode        TEXT,
            statut      TEXT DEFAULT 'envoyée',
            date_envoi  TEXT DEFAULT (to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')),
            notes       TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
 
 
# ── USERS ─────────────────────────────────────────────────────────────────────
 
def create_user(email: str, password_hash: str, nom: str, role: str = "client") -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, password, nom, role) VALUES (%s,%s,%s,%s) RETURNING id",
            (email, password_hash, nom, role)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        return -1
    finally:
        cur.close()
        conn.close()
 
 
def get_user_by_email(email: str) -> dict:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else {}
 
 
def get_user_by_id(user_id: int) -> dict:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else {}
 
 
def get_all_users() -> list:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
 
 
def toggle_user_actif(user_id: int, actif: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET actif=%s WHERE id=%s", (actif, user_id))
    conn.commit()
    cur.close()
    conn.close()
 
 
# ── PROFILS ───────────────────────────────────────────────────────────────────
 
def save_profil(nom, email, cv_path, profil_json: dict, user_id: int = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO profils (user_id, nom, email, cv_path, profil_json) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (user_id, nom, email, cv_path, json.dumps(profil_json, ensure_ascii=False))
    )
    profil_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return profil_id
 
 
def get_latest_profil(user_id: int = None) -> dict:
    """
    Retourne le dernier profil uploadé.
    - Avec user_id  → profil de ce user uniquement (cas nominal)
    - Sans user_id  → usage interne scheduler uniquement (ne jamais exposer en route)
    """
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if user_id:
        cur.execute(
            "SELECT * FROM profils WHERE user_id=%s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
    else:
        # Utilisé uniquement par le scheduler — retourne None pour forcer
        # l'itération par user dans scan_automatique()
        cur.close()
        conn.close()
        return {}
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {}
    d = dict(row)
    d["profil_json"] = json.loads(d["profil_json"])
    return d
 
 
def get_all_profils_actifs() -> list:
    """
    Retourne le dernier profil de chaque user actif.
    Utilisé par scan_automatique() pour itérer sur tous les clients.
    """
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT ON (p.user_id)
            p.*
        FROM profils p
        JOIN users u ON u.id = p.user_id
        WHERE u.actif = 1
        ORDER BY p.user_id, p.id DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["profil_json"] = json.loads(d["profil_json"])
        result.append(d)
    return result
 
 
# ── OFFRES ────────────────────────────────────────────────────────────────────
 
def save_offres(offres: list, profil_id: int, user_id: int = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    nb = 0
    for o in offres:
        try:
            cur.execute("""
                INSERT INTO offres
                  (profil_id, user_id, titre, entreprise, localisation, source, url, description,
                   score, resume_ia, match_stack, points_forts, points_faibles,
                   mode_candidature, email_contact, lettre_motivation, statut)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (user_id, url) DO NOTHING
            """, (
                profil_id, user_id,
                o.get("titre",""), o.get("entreprise",""), o.get("localisation",""),
                o.get("source",""), o.get("url",""), o.get("description",""),
                o.get("score",0), o.get("resume_ia",""), o.get("match_stack",""),
                o.get("points_forts",""), o.get("points_faibles",""),
                o.get("mode_candidature","formulaire"), o.get("email_contact",""),
                o.get("lettre_motivation",""), o.get("statut","ignoré")
            ))
            if cur.rowcount > 0:
                nb += 1
        except Exception:
            conn.rollback()
    conn.commit()
    cur.close()
    conn.close()
    return nb
 
 
def get_offres(profil_id: int, min_score: int = 0, statut: str = None, user_id: int = None) -> list:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if user_id:
        query = "SELECT * FROM offres WHERE user_id=%s AND score>=%s"
        params = [user_id, min_score]
    else:
        query = "SELECT * FROM offres WHERE profil_id=%s AND score>=%s"
        params = [profil_id, min_score]
    if statut:
        query += " AND statut=%s"
        params.append(statut)
    query += " ORDER BY score DESC, date_analyse DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
 
 
def get_offre(offre_id: int) -> dict:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM offres WHERE id=%s", (offre_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else {}
 
 
# ── CANDIDATURES ──────────────────────────────────────────────────────────────
 
def save_candidature(offre_id: int, profil_id: int, mode: str, notes: str = "", user_id: int = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO candidatures (offre_id, profil_id, user_id, mode, notes) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (offre_id, profil_id, user_id, mode, notes)
    )
    cand_id = cur.fetchone()[0]
    cur.execute("UPDATE offres SET statut='candidaté' WHERE id=%s", (offre_id,))
    conn.commit()
    cur.close()
    conn.close()
    return cand_id
 
 
def get_candidatures(profil_id: int, user_id: int = None) -> list:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if user_id:
        cur.execute("""
            SELECT c.*, o.titre, o.entreprise, o.score, o.url, o.mode_candidature
            FROM candidatures c
            JOIN offres o ON c.offre_id = o.id
            WHERE c.user_id=%s
            ORDER BY c.date_envoi DESC
        """, (user_id,))
    else:
        cur.execute("""
            SELECT c.*, o.titre, o.entreprise, o.score, o.url, o.mode_candidature
            FROM candidatures c
            JOIN offres o ON c.offre_id = o.id
            WHERE c.profil_id=%s
            ORDER BY c.date_envoi DESC
        """, (profil_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
 
 
def get_stats(profil_id: int, user_id: int = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    if user_id:
        cur.execute("SELECT COUNT(*) FROM offres WHERE user_id=%s", (user_id,))
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM offres WHERE user_id=%s AND statut='prêt'", (user_id,))
        pretes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM candidatures WHERE user_id=%s", (user_id,))
        envoyes = cur.fetchone()[0]
        cur.execute("SELECT MAX(score) FROM offres WHERE user_id=%s", (user_id,))
        top = cur.fetchone()[0]
    else:
        cur.execute("SELECT COUNT(*) FROM offres WHERE profil_id=%s", (profil_id,))
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM offres WHERE profil_id=%s AND statut='prêt'", (profil_id,))
        pretes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM candidatures WHERE profil_id=%s", (profil_id,))
        envoyes = cur.fetchone()[0]
        cur.execute("SELECT MAX(score) FROM offres WHERE profil_id=%s", (profil_id,))
        top = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"total": total, "pretes": pretes, "envoyes": envoyes, "top_score": top or 0}