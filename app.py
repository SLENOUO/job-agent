import os, json, threading, webbrowser
from functools import wraps
from flask import Flask, request, redirect, url_for, jsonify, session
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler

from config import UPLOADS_FOLDER, MIN_SCORE_AUTO_APPLY, MIN_SCORE_DISPLAY
from database import (
    init_db, save_profil, get_latest_profil,
    save_offres, get_offres, get_offre, save_candidature,
    get_candidatures, get_stats
)
from cv_parser import parse_cv
from scraper import run_all_scrapers
from agent import run_agent_pipeline
from mailer import envoyer_candidature, envoyer_notification

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "jobagent-secret-2026")
os.makedirs(UPLOADS_FOLDER, exist_ok=True)
init_db()

# === LOGIN ===
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "jobagent2026")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

BASE_STYLE = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;700&display=swap');
  :root {
    --bg:#080c14; --surface:#0f1729; --card:#131d35; --border:#1e2d4a;
    --blue:#3b82f6; --green:#10b981; --amber:#f59e0b; --red:#ef4444;
    --text:#e2e8f0; --muted:#64748b;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; min-height:100vh; }
  nav { background:var(--surface); border-bottom:1px solid var(--border); padding:0 32px;
        display:flex; align-items:center; gap:32px; height:60px; position:sticky; top:0; z-index:100; }
  nav .logo { font-family:'Space Mono',monospace; font-weight:700; color:var(--blue); font-size:16px; }
  nav a { color:var(--muted); text-decoration:none; font-size:14px; transition:color .2s; }
  nav a:hover, nav a.active { color:var(--text); }
  nav .logout { margin-left:auto; }
  .container { max-width:1100px; margin:0 auto; padding:32px 24px; }
  .page-title { font-size:28px; font-weight:700; margin-bottom:8px; }
  .page-sub { color:var(--muted); font-size:14px; margin-bottom:32px; }
  .stats-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:32px; }
  .stat-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; }
  .stat-card .val { font-size:36px; font-weight:700; font-family:'Space Mono',monospace; }
  .stat-card .lbl { color:var(--muted); font-size:13px; margin-top:4px; }
  .stat-card.blue .val { color:var(--blue); }
  .stat-card.green .val { color:var(--green); }
  .stat-card.amber .val { color:var(--amber); }
  .offre-card { background:var(--card); border:1px solid var(--border); border-radius:12px;
                padding:20px; margin-bottom:12px; display:flex; gap:16px; align-items:flex-start; }
  .offre-card:hover { border-color:var(--blue); }
  .score-badge { min-width:52px; height:52px; border-radius:10px; display:flex; align-items:center;
                 justify-content:center; font-family:'Space Mono',monospace; font-weight:700; font-size:18px; flex-shrink:0; }
  .score-badge.high   { background:rgba(16,185,129,.15); color:var(--green); border:1px solid rgba(16,185,129,.3); }
  .score-badge.medium { background:rgba(245,158,11,.15);  color:var(--amber); border:1px solid rgba(245,158,11,.3); }
  .score-badge.low    { background:rgba(100,116,139,.1);  color:var(--muted); border:1px solid var(--border); }
  .offre-content { flex:1; min-width:0; }
  .offre-titre { font-size:16px; font-weight:600; margin-bottom:4px; }
  .offre-meta  { color:var(--muted); font-size:13px; margin-bottom:8px; }
  .offre-resume { font-size:13px; color:#94a3b8; line-height:1.5; margin-bottom:10px; }
  .tag { display:inline-block; background:rgba(59,130,246,.15); color:#93c5fd;
         border:1px solid rgba(59,130,246,.2); border-radius:6px; padding:2px 8px; font-size:11px; margin:2px; }
  .btn { display:inline-block; padding:8px 16px; border-radius:8px; font-size:13px; font-weight:600;
         text-decoration:none; cursor:pointer; border:none; transition:all .2s; }
  .btn-primary { background:var(--blue); color:white; }
  .btn-primary:hover { background:#2563eb; }
  .btn-ghost { background:transparent; color:var(--muted); border:1px solid var(--border); }
  .btn-ghost:hover { border-color:var(--blue); color:var(--blue); }
  .btn-green { background:var(--green); color:white; }
  .btn-red { background:var(--red); color:white; }
  .upload-zone { border:2px dashed var(--border); border-radius:16px; padding:64px 32px;
                 text-align:center; cursor:pointer; transition:all .2s; background:var(--card); }
  .upload-zone:hover { border-color:var(--blue); }
  .lettre-box { background:#0a1628; border:1px solid var(--border); border-radius:12px;
                padding:24px; font-size:14px; line-height:1.8; white-space:pre-wrap; color:#cbd5e1; }
  .pill { display:inline-block; border-radius:999px; padding:3px 10px; font-size:11px; font-weight:600; }
  .pill.pret      { background:rgba(16,185,129,.15); color:var(--green); }
  .pill.candidaté { background:rgba(59,130,246,.15); color:var(--blue); }
  .pill.ignore    { background:rgba(100,116,139,.1);  color:var(--muted); }
  .spinner { display:inline-block; width:20px; height:20px; border:2px solid var(--border);
             border-top-color:var(--blue); border-radius:50%; animation:spin 1s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  input[type=file] { display:none; }
  .login-box { max-width:400px; margin:100px auto; background:var(--card);
               border:1px solid var(--border); border-radius:16px; padding:40px; }
  .form-group { margin-bottom:16px; }
  .form-group label { display:block; color:var(--muted); font-size:13px; margin-bottom:6px; }
  .form-group input { width:100%; background:var(--surface); border:1px solid var(--border);
                      border-radius:8px; padding:10px 14px; color:var(--text); font-size:14px; }
  .form-group input:focus { outline:none; border-color:var(--blue); }
  .error { background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.3);
           color:#fca5a5; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:16px; }
</style>
"""

def nav(active="d"):
    links = {
        "d": ("/", "Dashboard"),
        "u": ("/upload", "Upload CV"),
        "o": ("/offres", "Offres"),
        "c": ("/candidatures", "Candidatures"),
    }
    html = '<nav><span class="logo">⚡ JobAgent</span>'
    for key, (href, label) in links.items():
        cls = 'class="active"' if key == active else ""
        html += f'<a href="{href}" {cls}>{label}</a>'
    html += '<a href="/logout" class="logout btn-red" style="margin-left:auto;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;color:white;background:var(--red);text-decoration:none;">Déconnexion</a>'
    html += "</nav>"
    return html

def score_class(s):
    if s >= 8: return "high"
    if s >= 6: return "medium"
    return "low"


# ── LOGIN / LOGOUT ────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "Mot de passe incorrect."

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>JobAgent — Connexion</title>{BASE_STYLE}</head><body>
    <div class="login-box">
      <div style="text-align:center;margin-bottom:32px;">
        <div style="font-family:'Space Mono',monospace;font-weight:700;color:var(--blue);font-size:24px;">⚡ JobAgent</div>
        <p style="color:var(--muted);font-size:14px;margin-top:8px;">Accès sécurisé</p>
      </div>
      {"<div class='error'>" + error + "</div>" if error else ""}
      <form method="POST">
        <div class="form-group">
          <label>Mot de passe</label>
          <input type="password" name="password" placeholder="••••••••" autofocus>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;">
          Se connecter →
        </button>
      </form>
    </div>
    </body></html>"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    profil_row = get_latest_profil()
    if not profil_row:
        return redirect(url_for("upload"))
    profil_id = profil_row["id"]
    profil    = profil_row["profil_json"]
    stats     = get_stats(profil_id)
    top_offres= get_offres(profil_id, min_score=8)[:5]

    cards = ""
    for o in top_offres:
        sc   = o["score"]
        tags = "".join(f'<span class="tag">{t.strip()}</span>'
                       for t in (o.get("match_stack","") or "").split(",") if t.strip())
        cards += f"""
        <div class="offre-card">
          <div class="score-badge {score_class(sc)}">{sc}</div>
          <div class="offre-content">
            <div class="offre-titre">{o['titre']}</div>
            <div class="offre-meta">🏢 {o['entreprise']} · 📍 {o['localisation']} · 🔗 {o['source']}</div>
            <div class="offre-resume">{o.get('resume_ia','')}</div>
            <div style="margin-bottom:8px;">{tags}</div>
            <a href="/offre/{o['id']}" class="btn btn-ghost">Voir détail</a>
          </div>
        </div>"""

    nom = profil.get('nom','Candidat').split()[0] if profil.get('nom') else 'Candidat'

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>JobAgent</title>{BASE_STYLE}</head><body>
    {nav('d')}
    <div class="container">
      <h1 class="page-title">Bonjour, {nom} 👋</h1>
      <p class="page-sub">{profil.get('poste_recherche','')} · {profil.get('ecole','')} · Dispo {profil.get('disponibilite','')}</p>
      <div class="stats-grid">
        <div class="stat-card blue"><div class="val">{stats['total']}</div><div class="lbl">Offres analysées</div></div>
        <div class="stat-card green"><div class="val">{stats['pretes']}</div><div class="lbl">Candidatures prêtes</div></div>
        <div class="stat-card amber"><div class="val">{stats['envoyes']}</div><div class="lbl">Envoyées</div></div>
        <div class="stat-card"><div class="val">{stats['top_score']}/10</div><div class="lbl">Meilleur match</div></div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h2 style="font-size:18px;font-weight:600;">Top offres matchées</h2>
        <div style="display:flex;gap:8px;">
          <a href="/offres" class="btn btn-ghost">Voir toutes →</a>
          <button onclick="lancerScan()" class="btn btn-primary" id="scan-btn">🔍 Nouveau scan</button>
        </div>
      </div>
      {cards if cards else '<p style="color:var(--muted);text-align:center;padding:40px;">Lance un scan pour trouver des offres !</p>'}
    </div>
    <script>
    function lancerScan() {{
      const btn = document.getElementById('scan-btn');
      btn.innerHTML = '<span class="spinner"></span> Scan en cours...';
      btn.disabled = true;
      fetch('/run-scan', {{method:'POST'}})
        .then(r => r.json())
        .then(d => {{ btn.innerHTML='✅ ' + d.nb + ' offres'; setTimeout(()=>location.reload(),2000); }})
        .catch(() => {{ btn.innerHTML='❌ Erreur'; btn.disabled=false; }});
    }}
    </script>
    </body></html>"""


# ── UPLOAD ────────────────────────────────────────────────────────────────────

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Upload CV</title>{BASE_STYLE}</head><body>
    {nav('u')}
    <div class="container" style="max-width:600px;">
      <h1 class="page-title">Upload ton CV</h1>
      <p class="page-sub">L'agent va extraire ton profil et lancer la recherche automatiquement.</p>
      <form id="form" action="/upload" method="POST" enctype="multipart/form-data">
        <label for="cv-input">
          <div class="upload-zone">
            <div style="font-size:48px;">📄</div>
            <div style="font-size:20px;font-weight:600;margin:16px 0 8px;">Glisse ton CV ici</div>
            <div style="color:var(--muted);font-size:14px;">ou clique pour sélectionner · PDF uniquement</div>
          </div>
        </label>
        <input type="file" id="cv-input" name="cv" accept=".pdf" onchange="handleFile(this)">
        <button type="submit" class="btn btn-primary" id="submit-btn"
                style="width:100%;padding:14px;margin-top:16px;font-size:15px;display:none;">
          🚀 Analyser mon CV et lancer l'agent
        </button>
      </form>
      <div id="loading" style="display:none;text-align:center;padding:40px;">
        <div class="spinner" style="width:40px;height:40px;margin:0 auto 16px;border-width:3px;"></div>
        <p style="color:var(--muted);" id="loading-msg">Extraction du CV...</p>
      </div>
    </div>
    <script>
    function handleFile(input) {{
      if (input.files[0]) document.getElementById('submit-btn').style.display='block';
    }}
    document.getElementById('form').onsubmit = function() {{
      document.getElementById('form').style.display='none';
      document.getElementById('loading').style.display='block';
      const msgs = ["Extraction du CV...","Analyse IA du profil...","Recherche des offres...","Scoring et matching...","Génération des lettres..."];
      let i=0;
      setInterval(()=>{{ if(i<msgs.length) document.getElementById('loading-msg').textContent=msgs[i++]; }},4000);
    }};
    </script>
    </body></html>"""


@app.route("/upload", methods=["POST"])
@login_required
def upload_post():
    f = request.files.get("cv")
    if not f or not f.filename.endswith(".pdf"):
        return redirect(url_for("upload"))
    filename = secure_filename(f.filename)
    cv_path  = os.path.join(UPLOADS_FOLDER, filename)
    f.save(cv_path)
    profil    = parse_cv(cv_path)
    profil_id = save_profil(profil.get("nom","Candidat"), profil.get("email",""), cv_path, profil)

    def pipeline():
        offres   = run_all_scrapers()
        analyses = run_agent_pipeline(offres, profil)
        save_offres(analyses, profil_id)
        envoyer_notification(profil, get_stats(profil_id))

    threading.Thread(target=pipeline, daemon=True).start()
    return redirect(url_for("dashboard"))


# ── OFFRES ────────────────────────────────────────────────────────────────────

@app.route("/offres")
@login_required
def offres():
    profil_row = get_latest_profil()
    if not profil_row:
        return redirect(url_for("upload"))
    profil_id = profil_row["id"]
    filtre    = request.args.get("filtre","toutes")
    statut_map = {"pretes":"prêt","candidatees":"candidaté"}
    liste = get_offres(profil_id, statut=statut_map.get(filtre))

    cards = ""
    for o in liste:
        sc   = o["score"]
        tags = "".join(f'<span class="tag">{t.strip()}</span>'
                       for t in (o.get("match_stack","") or "").split(",") if t.strip())
        cards += f"""
        <div class="offre-card">
          <div class="score-badge {score_class(sc)}">{sc}</div>
          <div class="offre-content">
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;">
              <div class="offre-titre">{o['titre']}</div>
              <span class="pill {'pret' if o['statut']=='prêt' else 'candidaté' if o['statut']=='candidaté' else 'ignore'}">{o['statut']}</span>
            </div>
            <div class="offre-meta">🏢 {o['entreprise']} · 📍 {o['localisation']} · 🔗 {o['source']}</div>
            <div class="offre-resume">{o.get('resume_ia','')}</div>
            <div style="margin-bottom:10px;">{tags}</div>
            <a href="/offre/{o['id']}" class="btn btn-ghost" style="margin-right:8px;">Voir détail</a>
            {"<a href='/postuler/" + str(o['id']) + "' class='btn btn-green'>Postuler →</a>" if o['statut']=='prêt' else ""}
          </div>
        </div>"""

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Offres</title>{BASE_STYLE}</head><body>
    {nav('o')}
    <div class="container">
      <h1 class="page-title">Offres analysées</h1>
      <div style="display:flex;gap:8px;margin-bottom:24px;">
        <a href="/offres" class="btn {'btn-primary' if filtre=='toutes' else 'btn-ghost'}">Toutes</a>
        <a href="/offres?filtre=pretes" class="btn {'btn-primary' if filtre=='pretes' else 'btn-ghost'}">✅ Prêtes</a>
        <a href="/offres?filtre=candidatees" class="btn {'btn-primary' if filtre=='candidatees' else 'btn-ghost'}">📨 Candidatées</a>
      </div>
      {cards if cards else '<p style="color:var(--muted);text-align:center;padding:60px;">Aucune offre trouvée.</p>'}
    </div></body></html>"""


# ── DETAIL OFFRE ──────────────────────────────────────────────────────────────

@app.route("/offre/<int:offre_id>")
@login_required
def detail_offre(offre_id):
    offre = get_offre(offre_id)
    if not offre:
        return redirect(url_for("offres"))
    sc   = offre["score"]
    tags = "".join(f'<span class="tag">{t.strip()}</span>'
                   for t in (offre.get("match_stack","") or "").split(",") if t.strip())
    lettre = offre.get("lettre_motivation","") or "Lettre non générée (score < 8)."

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>{offre['titre']}</title>{BASE_STYLE}</head><body>
    {nav('o')}
    <div class="container" style="max-width:800px;">
      <a href="/offres" style="color:var(--muted);text-decoration:none;font-size:13px;">← Retour</a>
      <div style="display:flex;gap:20px;margin:24px 0 8px;">
        <div class="score-badge {score_class(sc)}" style="width:64px;height:64px;font-size:22px;">{sc}/10</div>
        <div>
          <h1 style="font-size:22px;font-weight:700;">{offre['titre']}</h1>
          <p style="color:var(--muted);margin-top:4px;">🏢 {offre['entreprise']} · 📍 {offre['localisation']}</p>
        </div>
      </div>
      <div style="margin:16px 0;">{tags}</div>
      <p style="color:#94a3b8;font-size:14px;margin-bottom:24px;">{offre.get('resume_ia','')}</p>
      <div style="margin-bottom:24px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h2 style="font-size:16px;font-weight:600;">✉️ Lettre de motivation</h2>
          <button onclick="copyLM()" class="btn btn-ghost" id="copy-btn">Copier</button>
        </div>
        <div class="lettre-box" id="lettre">{lettre}</div>
      </div>
      <div style="display:flex;gap:12px;">
        <a href="{offre['url']}" target="_blank" class="btn btn-ghost">🌐 Voir l'offre</a>
        {"<a href='/postuler/" + str(offre['id']) + "' class='btn btn-green'>🚀 Postuler</a>" if offre['statut']=='prêt' else '<span class="pill candidaté" style="padding:8px 16px;">✅ Déjà candidaté</span>'}
      </div>
    </div>
    <script>
    function copyLM() {{
      navigator.clipboard.writeText(document.getElementById('lettre').innerText)
        .then(()=>{{ document.getElementById('copy-btn').textContent='✅ Copié!'; setTimeout(()=>document.getElementById('copy-btn').textContent='Copier',2000); }});
    }}
    </script>
    </body></html>"""


# ── POSTULER ──────────────────────────────────────────────────────────────────

@app.route("/postuler/<int:offre_id>")
@login_required
def postuler(offre_id):
    profil_row = get_latest_profil()
    offre      = get_offre(offre_id)
    if not offre or not profil_row:
        return redirect(url_for("offres"))
    profil    = profil_row["profil_json"]
    profil_id = profil_row["id"]
    mode      = offre.get("mode_candidature","formulaire")
    notes     = ""
    if mode == "email" and offre.get("email_contact"):
        ok    = envoyer_candidature(offre, profil, profil_row.get("cv_path",""))
        notes = "Email envoyé" if ok else "Échec envoi"
    else:
        webbrowser.open(offre["url"])
        notes = "Formulaire ouvert dans le navigateur"
    save_candidature(offre_id, profil_id, mode, notes)
    return redirect(url_for("detail_offre", offre_id=offre_id))


# ── CANDIDATURES ──────────────────────────────────────────────────────────────

@app.route("/candidatures")
@login_required
def candidatures():
    profil_row = get_latest_profil()
    if not profil_row:
        return redirect(url_for("upload"))
    liste = get_candidatures(profil_row["id"])
    cards = ""
    for c in liste:
        cards += f"""
        <div class="offre-card">
          <div class="score-badge {score_class(c['score'])}">{c['score']}</div>
          <div class="offre-content">
            <div class="offre-titre">{c['titre']}</div>
            <div class="offre-meta">🏢 {c['entreprise']} · 📅 {c['date_envoi'][:10]} · <span class="pill candidaté">candidaté</span></div>
            <a href="{c['url']}" target="_blank" class="btn btn-ghost" style="margin-top:8px;">Voir l'offre</a>
          </div>
        </div>"""

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Candidatures</title>{BASE_STYLE}</head><body>
    {nav('c')}
    <div class="container">
      <h1 class="page-title">Candidatures envoyées</h1>
      <p class="page-sub">{len(liste)} candidature(s)</p>
      {cards if cards else '<p style="color:var(--muted);text-align:center;padding:60px;">Aucune candidature encore.</p>'}
    </div></body></html>"""


# ── RUN SCAN ──────────────────────────────────────────────────────────────────

@app.route("/run-scan", methods=["POST"])
@login_required
def run_scan():
    profil_row = get_latest_profil()
    if not profil_row:
        return jsonify({"error":"Aucun profil"}), 400
    profil    = profil_row["profil_json"]
    profil_id = profil_row["id"]
    offres    = run_all_scrapers()
    analyses  = run_agent_pipeline(offres, profil)
    nb        = save_offres(analyses, profil_id)
    return jsonify({"nb": nb, "total": len(analyses)})


# ── SCHEDULER ─────────────────────────────────────────────────────────────────

def scan_automatique():
    print("[Scheduler] Scan automatique lancé...")
    profil_row = get_latest_profil()
    if not profil_row:
        print("[Scheduler] Aucun profil trouvé.")
        return
    profil    = profil_row["profil_json"]
    profil_id = profil_row["id"]
    offres    = run_all_scrapers()
    analyses  = run_agent_pipeline(offres, profil)
    nb        = save_offres(analyses, profil_id)
    envoyer_notification(profil, get_stats(profil_id))
    print(f"[Scheduler] Terminé — {nb} nouvelles offres.")

scheduler = BackgroundScheduler()
scheduler.add_job(scan_automatique, 'cron', hour=8, minute=0)
scheduler.start()

if __name__ == "__main__":
    print("\n🚀 JobAgent démarré → http://localhost:5000")
    print("⏰ Scan automatique programmé chaque matin à 8h00\n")
    app.run(debug=False, port=5000)