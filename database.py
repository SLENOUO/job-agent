import sqlite3, os, json
from config import DB_PATH

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS profils (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nom         TEXT,
            email       TEXT,
            cv_path     TEXT,
            profil_json TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS offres (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            profil_id         INTEGER,
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
            date_analyse      TEXT DEFAULT (datetime('now')),
            UNIQUE(profil_id, url)
        );

        CREATE TABLE IF NOT EXISTS candidatures (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            offre_id    INTEGER,
            profil_id   INTEGER,
            mode        TEXT,
            statut      TEXT DEFAULT 'envoyée',
            date_envoi  TEXT DEFAULT (datetime('now')),
            notes       TEXT
        );
    """)
    conn.commit()
    conn.close()

def save_profil(nom, email, cv_path, profil_json: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO profils (nom, email, cv_path, profil_json) VALUES (?,?,?,?)",
        (nom, email, cv_path, json.dumps(profil_json, ensure_ascii=False))
    )
    profil_id = cur.lastrowid
    conn.commit()
    conn.close()
    return profil_id

def get_latest_profil() -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM profils ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return {}
    d = dict(row)
    d["profil_json"] = json.loads(d["profil_json"])
    return d

def save_offres(offres: list, profil_id: int) -> int:
    conn = get_conn()
    nb = 0
    for o in offres:
        try:
            conn.execute("""
                INSERT INTO offres
                  (profil_id, titre, entreprise, localisation, source, url, description,
                   score, resume_ia, match_stack, points_forts, points_faibles,
                   mode_candidature, email_contact, lettre_motivation, statut)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                profil_id,
                o.get("titre",""), o.get("entreprise",""), o.get("localisation",""),
                o.get("source",""), o.get("url",""), o.get("description",""),
                o.get("score",0), o.get("resume_ia",""), o.get("match_stack",""),
                o.get("points_forts",""), o.get("points_faibles",""),
                o.get("mode_candidature","formulaire"), o.get("email_contact",""),
                o.get("lettre_motivation",""), o.get("statut","ignoré")
            ))
            nb += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return nb

def get_offres(profil_id: int, min_score: int = 0, statut: str = None) -> list:
    conn = get_conn()
    query = "SELECT * FROM offres WHERE profil_id=? AND score>=?"
    params = [profil_id, min_score]
    if statut:
        query += " AND statut=?"
        params.append(statut)
    query += " ORDER BY score DESC, date_analyse DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_offre(offre_id: int) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM offres WHERE id=?", (offre_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def save_candidature(offre_id: int, profil_id: int, mode: str, notes: str = "") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO candidatures (offre_id, profil_id, mode, notes) VALUES (?,?,?,?)",
        (offre_id, profil_id, mode, notes)
    )
    conn.execute("UPDATE offres SET statut='candidaté' WHERE id=?", (offre_id,))
    cand_id = cur.lastrowid
    conn.commit()
    conn.close()
    return cand_id

def get_candidatures(profil_id: int) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.*, o.titre, o.entreprise, o.score, o.url, o.mode_candidature
        FROM candidatures c
        JOIN offres o ON c.offre_id = o.id
        WHERE c.profil_id=?
        ORDER BY c.date_envoi DESC
    """, (profil_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats(profil_id: int) -> dict:
    conn = get_conn()
    total   = conn.execute("SELECT COUNT(*) FROM offres WHERE profil_id=?", (profil_id,)).fetchone()[0]
    pretes  = conn.execute("SELECT COUNT(*) FROM offres WHERE profil_id=? AND statut='prêt'", (profil_id,)).fetchone()[0]
    envoyes = conn.execute("SELECT COUNT(*) FROM candidatures WHERE profil_id=?", (profil_id,)).fetchone()[0]
    top     = conn.execute("SELECT MAX(score) FROM offres WHERE profil_id=?", (profil_id,)).fetchone()[0]
    conn.close()
    return {"total": total, "pretes": pretes, "envoyes": envoyes, "top_score": top or 0}