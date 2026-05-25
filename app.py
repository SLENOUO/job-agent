import os, json, threading, webbrowser, tempfile, re
from functools import wraps
from flask import Flask, request, redirect, url_for, jsonify, session, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib import colors

from config import UPLOADS_FOLDER, MIN_SCORE_AUTO_APPLY, MIN_SCORE_DISPLAY
from database import (
    init_db, get_conn, save_profil, get_latest_profil,
    save_offres, get_offres, get_offre, save_candidature,
    get_candidatures, get_stats,
    create_user, get_user_by_email, get_user_by_id,
    get_all_users, toggle_user_actif,
    get_all_profils_actifs,
    is_trial_active, is_trial_expired, days_left_trial
)
from cv_parser import parse_cv
from scraper import run_all_scrapers
from agent import run_agent_pipeline
from mailer import envoyer_candidature, envoyer_notification
from landing import landing as landing_bp
from payment import payment as payment_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "jobagent-secret-2026")
os.makedirs(UPLOADS_FOLDER, exist_ok=True)
init_db()
app.register_blueprint(landing_bp)
app.register_blueprint(payment_bp)

ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", "admin@jobagent.fr")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "jobagent2026")

def create_admin():
    existing = get_user_by_email(ADMIN_EMAIL)
    if not existing:
        create_user(ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), "Admin", role="admin")
        print(f"[Admin] Compte admin créé : {ADMIN_EMAIL}")

create_admin()


# ─────────────────────────────────────────────
#  DECORATEURS
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        user = get_user_by_id(session["user_id"])
        if not user:
            session.clear()
            return redirect(url_for("login"))
        # Admin → toujours accès
        if user.get("role") == "admin":
            return f(*args, **kwargs)
        # Trial expiré → redirection checkout
        if is_trial_expired(user):
            session.clear()
            return redirect(url_for("trial_expired"))
        # Compte inactif (abonné désactivé)
        if not user.get("actif"):
            session.clear()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        user = get_user_by_id(session["user_id"])
        if not user or user.get("role") != "admin":
            return redirect(url_for("dashboard"))
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
  .auth-box { max-width:420px; margin:80px auto; background:var(--card);
              border:1px solid var(--border); border-radius:16px; padding:40px; }
  .form-group { margin-bottom:16px; }
  .form-group label { display:block; color:var(--muted); font-size:13px; margin-bottom:6px; }
  .form-group input, .form-group select {
    width:100%; background:var(--surface); border:1px solid var(--border);
    border-radius:8px; padding:10px 14px; color:var(--text); font-size:14px; }
  .form-group input:focus, .form-group select:focus { outline:none; border-color:var(--blue); }
  .error { background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.3);
           color:#fca5a5; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:16px; }
  .success { background:rgba(16,185,129,.1); border:1px solid rgba(16,185,129,.3);
             color:#6ee7b7; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:16px; }
  .trial-banner { background:rgba(245,158,11,.1); border:1px solid rgba(245,158,11,.3);
                  color:var(--amber); border-radius:8px; padding:10px 16px; font-size:13px;
                  margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; }
  table { width:100%; border-collapse:collapse; }
  table th { text-align:left; color:var(--muted); font-size:12px; padding:8px 12px;
             border-bottom:1px solid var(--border); }
  table td { padding:12px; border-bottom:1px solid var(--border); font-size:14px; }
  table tr:hover td { background:var(--card); }
</style>
"""

def nav(active="d", is_admin=False, user=None):
    links = {
        "d": ("/", "Dashboard"),
        "u": ("/upload", "Upload CV"),
        "o": ("/offres", "Offres"),
        "c": ("/candidatures", "Candidatures"),
    }
    html = '<nav><span class="logo">⚡ LENOUO</span>'
    for key, (href, label) in links.items():
        cls = 'class="active"' if key == active else ""
        html += f'<a href="{href}" {cls}>{label}</a>'
    if is_admin:
        cls = 'class="active"' if active == "admin" else ""
        html += f'<a href="/admin" {cls} style="color:var(--amber);">⚙️ Admin</a>'
    # Badge trial
    if user and is_trial_active(user):
        jours = days_left_trial(user)
        html += f'<span style="margin-left:auto;background:rgba(245,158,11,.15);color:var(--amber);border:1px solid rgba(245,158,11,.3);border-radius:999px;padding:4px 12px;font-size:12px;font-weight:600;">⏳ Essai — {jours}j restants</span>'
        html += '<a href="/logout" style="margin-left:12px;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;color:white;background:var(--red);text-decoration:none;">Déconnexion</a>'
    else:
        html += '<a href="/logout" style="margin-left:auto;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:600;color:white;background:var(--red);text-decoration:none;">Déconnexion</a>'
    html += "</nav>"
    return html

def score_class(s):
    if s >= 8: return "high"
    if s >= 6: return "medium"
    return "low"

def current_user():
    uid = session.get("user_id")
    if uid:
        return get_user_by_id(uid)
    return {}

def nettoyer_lettre_pdf(texte: str) -> str:
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^#{1,6}\s*.*?\n', '', texte, flags=re.MULTILINE)
    texte = re.sub(r'-{2,}', '', texte)
    texte = re.sub(r'^Objet\s*:.*?\n', '', texte, flags=re.MULTILINE)
    texte = re.sub(r'Lettre de motivation\s*\n?', '', texte, flags=re.IGNORECASE)
    texte = re.sub(r'\n{3,}', '\n\n', texte)
    return texte.strip()


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user     = get_user_by_email(email)
        if user and check_password_hash(user["password"], password):
            # Vérif trial expiré
            if is_trial_expired(user):
                return redirect(url_for("trial_expired"))
            if not user.get("actif") and user.get("role") != "admin":
                error = "Compte désactivé. Contactez le support."
            else:
                session["user_id"]   = user["id"]
                session["user_role"] = user["role"]
                session["user_nom"]  = user["nom"]
                return redirect(url_for("dashboard"))
        else:
            error = "Email ou mot de passe incorrect."

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>LENOUO — Connexion</title>{BASE_STYLE}</head><body>
    <div class="auth-box">
      <div style="text-align:center;margin-bottom:32px;">
        <div style="font-family:'Space Mono',monospace;font-weight:700;color:var(--blue);font-size:24px;">⚡ LENOUO</div>
        <p style="color:var(--muted);font-size:14px;margin-top:8px;">Connectez-vous à votre compte</p>
      </div>
      {"<div class='error'>" + error + "</div>" if error else ""}
      <form method="POST">
        <div class="form-group"><label>Email</label>
          <input type="email" name="email" placeholder="vous@email.com" autofocus></div>
        <div class="form-group"><label>Mot de passe</label>
          <input type="password" name="password" placeholder="••••••••"></div>
        <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;margin-top:8px;">
          Se connecter →</button>
      </form>
      <div style="text-align:center;margin-top:20px;">
        <a href="/register-trial" style="color:var(--green);font-size:13px;font-weight:600;text-decoration:none;">
          🎁 Essai gratuit 30 jours — Créer un compte</a>
      </div>
      <p style="text-align:center;color:var(--muted);font-size:13px;margin-top:12px;">
        Abonnement ? <a href="/checkout" style="color:var(--blue);">8,99€/mois →</a></p>
    </div></body></html>"""


@app.route("/trial-expired")
def trial_expired():
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Essai terminé</title>{BASE_STYLE}</head><body>
    <div class="auth-box" style="text-align:center;">
      <div style="font-size:48px;margin-bottom:16px;">⏰</div>
      <div style="font-family:'Space Mono',monospace;font-weight:700;color:var(--blue);font-size:22px;margin-bottom:16px;">LENOUO</div>
      <h2 style="font-size:22px;font-weight:700;margin-bottom:12px;">Ton essai gratuit est terminé</h2>
      <p style="color:var(--muted);font-size:14px;margin-bottom:32px;line-height:1.6;">
        Tu as utilisé tes 30 jours d'essai gratuit. Passe à l'abonnement pour continuer à recevoir des offres personnalisées chaque jour.
      </p>
      <a href="/checkout" class="btn btn-primary" style="display:block;padding:14px;font-size:15px;margin-bottom:12px;">
        Continuer pour 8,99€/mois →</a>
      <a href="/login" style="color:var(--muted);font-size:13px;">← Retour connexion</a>
    </div></body></html>"""


@app.route("/register-trial", methods=["GET", "POST"])
def register_trial():
    """Inscription avec essai gratuit 30 jours — sans Stripe."""
    error = ""
    if request.method == "POST":
        nom      = request.form.get("nom", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if not nom or not email or not password:
            error = "Tous les champs sont obligatoires."
        elif password != confirm:
            error = "Les mots de passe ne correspondent pas."
        elif len(password) < 6:
            error = "Le mot de passe doit faire au moins 6 caractères."
        else:
            uid = create_user(email, generate_password_hash(password), nom, is_trial=True)
            if uid == -1:
                error = "Cet email est déjà utilisé."
            else:
                user = get_user_by_email(email)
                session["user_id"]   = user["id"]
                session["user_role"] = user["role"]
                session["user_nom"]  = user["nom"]
                return redirect(url_for("upload"))

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>LENOUO — Essai gratuit</title>{BASE_STYLE}</head><body>
    <div class="auth-box">
      <div style="text-align:center;margin-bottom:32px;">
        <div style="font-size:36px;margin-bottom:8px;">🎁</div>
        <div style="font-family:'Space Mono',monospace;font-weight:700;color:var(--blue);font-size:22px;">LENOUO</div>
        <p style="color:var(--green);font-size:14px;margin-top:8px;font-weight:600;">Essai gratuit — 30 jours</p>
        <p style="color:var(--muted);font-size:13px;margin-top:4px;">Sans carte bancaire · Sans engagement</p>
      </div>
      {"<div class='error'>" + error + "</div>" if error else ""}
      <form method="POST">
        <div class="form-group"><label>Nom complet</label>
          <input type="text" name="nom" placeholder="Prénom Nom" autofocus></div>
        <div class="form-group"><label>Email</label>
          <input type="email" name="email" placeholder="vous@email.com"></div>
        <div class="form-group"><label>Mot de passe</label>
          <input type="password" name="password" placeholder="••••••••"></div>
        <div class="form-group"><label>Confirmer le mot de passe</label>
          <input type="password" name="confirm" placeholder="••••••••"></div>
        <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;margin-top:8px;">
          🚀 Démarrer mon essai gratuit</button>
      </form>
      <p style="text-align:center;color:var(--muted);font-size:13px;margin-top:16px;">
        Déjà un compte ? <a href="/login" style="color:var(--blue);">Se connecter</a></p>
    </div></body></html>"""


@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    stripe_session_id = request.args.get("session_id", "")

    paid = False
    customer_email = ""
    if stripe_session_id:
        try:
            import stripe as stripe_lib
            stripe_lib.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            stripe_session = stripe_lib.checkout.Session.retrieve(stripe_session_id)
            if stripe_session.payment_status == "paid":
                paid = True
                customer_email = stripe_session.customer_details.email or ""
        except Exception:
            pass

    if not stripe_session_id or not paid:
        return redirect(url_for("landing.home"))

    if request.method == "POST":
        nom      = request.form.get("nom", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if not nom or not email or not password:
            error = "Tous les champs sont obligatoires."
        elif password != confirm:
            error = "Les mots de passe ne correspondent pas."
        elif len(password) < 6:
            error = "Le mot de passe doit faire au moins 6 caractères."
        else:
            uid = create_user(email, generate_password_hash(password), nom)
            if uid == -1:
                error = "Cet email est déjà utilisé."
            else:
                user = get_user_by_email(email)
                session["user_id"]   = user["id"]
                session["user_role"] = user["role"]
                session["user_nom"]  = user["nom"]
                return redirect(url_for("upload"))

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>LENOUO — Finaliser mon compte</title>{BASE_STYLE}</head><body>
    <div class="auth-box">
      <div style="text-align:center;margin-bottom:32px;">
        <div style="font-size:40px;margin-bottom:12px;">🎉</div>
        <div style="font-family:'Space Mono',monospace;font-weight:700;color:var(--blue);font-size:24px;">⚡ LENOUO</div>
        <p style="color:var(--green);font-size:14px;margin-top:8px;font-weight:600;">✓ Paiement confirmé</p>
        <p style="color:var(--muted);font-size:13px;margin-top:4px;">Crée ton compte pour accéder à l'agent</p>
      </div>
      {"<div class='error'>" + error + "</div>" if error else ""}
      <form method="POST" action="/register?session_id={stripe_session_id}">
        <div class="form-group"><label>Nom complet</label>
          <input type="text" name="nom" placeholder="Prénom Nom" autofocus></div>
        <div class="form-group"><label>Email</label>
          <input type="email" name="email" value="{customer_email}" placeholder="vous@email.com"></div>
        <div class="form-group"><label>Mot de passe</label>
          <input type="password" name="password" placeholder="••••••••"></div>
        <div class="form-group"><label>Confirmer le mot de passe</label>
          <input type="password" name="confirm" placeholder="••••••••"></div>
        <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;margin-top:8px;">
          Créer mon compte →</button>
      </form>
    </div></body></html>"""


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────
#  ADMIN
# ─────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin():
    users = get_all_users()
    rows = ""
    for u in users:
        statut     = "✅ Actif" if u["actif"] else "❌ Inactif"
        action     = "Désactiver" if u["actif"] else "Activer"
        action_url = f"/admin/toggle/{u['id']}"
        trial_info = f"⏳ {u['trial_end']}" if u.get("trial_end") else "—"
        rows += f"""<tr>
          <td>{u['nom']}</td><td>{u['email']}</td>
          <td><span style="color:{'var(--green)' if u['actif'] else 'var(--red)'}">{statut}</span></td>
          <td>{u['role']}</td>
          <td style="color:var(--amber);font-size:12px;">{trial_info}</td>
          <td>{u['created_at'][:10]}</td>
          <td><a href="{action_url}" class="btn btn-ghost" style="font-size:12px;">{action}</a></td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Admin</title>{BASE_STYLE}</head><body>
    {nav('admin', is_admin=True)}
    <div class="container">
      <h1 class="page-title">⚙️ Administration</h1>
      <p class="page-sub">{len(users)} utilisateur(s) enregistré(s)</p>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h2 style="font-size:18px;font-weight:600;">Utilisateurs</h2>
        <div style="display:flex;gap:8px;">
          <a href="/admin/purge-zero" class="btn btn-ghost" style="color:var(--red);border-color:var(--red);">🗑️ Purger scores 0</a>
          <a href="/admin/create" class="btn btn-primary">+ Créer un utilisateur</a>
        </div>
      </div>
      <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;">
        <table><thead><tr>
          <th>Nom</th><th>Email</th><th>Statut</th><th>Rôle</th><th>Trial fin</th><th>Créé le</th><th>Action</th>
        </tr></thead><tbody>{rows}</tbody></table>
      </div>
    </div></body></html>"""


@app.route("/admin/purge-zero")
@admin_required
def purge_zero():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM offres WHERE score = 0")
    nb = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Purge</title>{BASE_STYLE}</head><body>
    {nav('admin', is_admin=True)}
    <div class="container" style="max-width:500px;text-align:center;padding-top:80px;">
      <div style="font-size:48px;margin-bottom:16px;">🗑️</div>
      <h1 class="page-title">{nb} offres supprimées</h1>
      <p class="page-sub">Toutes les offres avec score 0 ont été purgées.</p>
      <a href="/upload" class="btn btn-primary" style="margin-top:24px;">
        Uploader un CV pour relancer →</a>
    </div></body></html>"""


@app.route("/admin/toggle/<int:user_id>")
@admin_required
def toggle_user(user_id):
    user = get_user_by_id(user_id)
    if user:
        toggle_user_actif(user_id, 0 if user["actif"] else 1)
    return redirect(url_for("admin"))


@app.route("/admin/create", methods=["GET", "POST"])
@admin_required
def admin_create_user():
    error = ""
    success = ""
    if request.method == "POST":
        nom      = request.form.get("nom", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role     = request.form.get("role", "client")
        trial    = request.form.get("trial", "0") == "1"
        uid      = create_user(email, generate_password_hash(password), nom, role, is_trial=trial)
        if uid == -1:
            error = "Cet email est déjà utilisé."
        else:
            success = f"Utilisateur {nom} créé {'(essai 30j)' if trial else ''}."

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Créer utilisateur</title>{BASE_STYLE}</head><body>
    {nav('admin', is_admin=True)}
    <div class="container" style="max-width:500px;">
      <h1 class="page-title">Créer un utilisateur</h1>
      {"<div class='error'>" + error + "</div>" if error else ""}
      {"<div class='success'>" + success + "</div>" if success else ""}
      <form method="POST" style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;">
        <div class="form-group"><label>Nom complet</label>
          <input type="text" name="nom" placeholder="Prénom Nom"></div>
        <div class="form-group"><label>Email</label>
          <input type="email" name="email" placeholder="client@email.com"></div>
        <div class="form-group"><label>Mot de passe</label>
          <input type="password" name="password" placeholder="••••••••"></div>
        <div class="form-group"><label>Rôle</label>
          <select name="role">
            <option value="client">Client</option>
            <option value="admin">Admin</option>
          </select></div>
        <div class="form-group" style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" name="trial" value="1" id="trial" style="width:auto;">
          <label for="trial" style="margin:0;cursor:pointer;">Essai gratuit 30 jours</label>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;">
          Créer l'utilisateur →</button>
      </form>
      <a href="/admin" style="display:block;text-align:center;margin-top:16px;color:var(--muted);font-size:13px;">← Retour admin</a>
    </div></body></html>"""


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    user       = current_user()
    user_id    = user["id"]
    is_admin   = user.get("role") == "admin"
    profil_row = get_latest_profil(user_id=user_id)
    if not profil_row:
        return redirect(url_for("upload"))
    profil_id  = profil_row["id"]
    profil     = profil_row["profil_json"]
    stats      = get_stats(profil_id, user_id=user_id)
    top_offres = get_offres(profil_id, min_score=8, user_id=user_id)[:5]

    # Bannière trial
    trial_banner = ""
    if is_trial_active(user):
        jours = days_left_trial(user)
        trial_banner = f"""
        <div class="trial-banner">
          <span>🎁 Essai gratuit — <strong>{jours} jour(s) restant(s)</strong></span>
          <a href="/checkout" class="btn btn-primary" style="padding:6px 14px;font-size:12px;">
            S'abonner 8,99€/mois →</a>
        </div>"""

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

    nom = profil.get('nom','').split()[0] if profil.get('nom') else user.get('nom','Candidat').split()[0]

    mots_cles = profil.get("mots_cles_recherche", [])
    keywords_html = ""
    if mots_cles:
        kw_tags = "".join(f'<span class="tag">{kw}</span>' for kw in mots_cles)
        keywords_html = f"""
        <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;
                    padding:16px 20px;margin-bottom:24px;">
          <div style="color:var(--muted);font-size:12px;margin-bottom:8px;">🔍 Mots-clés extraits de ton CV</div>
          <div>{kw_tags}</div>
        </div>"""

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>LENOUO</title>{BASE_STYLE}</head><body>
    {nav('d', is_admin=is_admin, user=user)}
    <div class="container">
      {trial_banner}
      <h1 class="page-title">Bonjour, {nom} 👋</h1>
      <p class="page-sub">{profil.get('poste_recherche','')} · {profil.get('ecole','')} · Dispo {profil.get('disponibilite','')}</p>
      <div class="stats-grid">
        <div class="stat-card blue"><div class="val">{stats['total']}</div><div class="lbl">Offres analysées</div></div>
        <div class="stat-card green"><div class="val">{stats['pretes']}</div><div class="lbl">Candidatures prêtes</div></div>
        <div class="stat-card amber"><div class="val">{stats['envoyes']}</div><div class="lbl">Envoyées</div></div>
        <div class="stat-card"><div class="val">{stats['top_score']}/10</div><div class="lbl">Meilleur match</div></div>
      </div>
      {keywords_html}
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


# ─────────────────────────────────────────────
#  UPLOAD CV
# ─────────────────────────────────────────────

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    user     = current_user()
    is_admin = user.get("role") == "admin"
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Upload CV</title>{BASE_STYLE}</head><body>
    {nav('u', is_admin=is_admin, user=user)}
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
          🚀 Analyser mon CV et lancer l'agent</button>
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
      const msgs = ["Extraction du CV...","Analyse IA du profil...","Génération des mots-clés...","Recherche des offres...","Scoring et matching...","Génération des lettres..."];
      let i=0;
      setInterval(()=>{{ if(i<msgs.length) document.getElementById('loading-msg').textContent=msgs[i++]; }},4000);
    }};
    </script>
    </body></html>"""


@app.route("/upload", methods=["POST"])
@login_required
def upload_post():
    user    = current_user()
    user_id = user["id"]
    f = request.files.get("cv")
    if not f or not f.filename.endswith(".pdf"):
        return redirect(url_for("upload"))
    filename  = secure_filename(f.filename)
    cv_path   = os.path.join(UPLOADS_FOLDER, filename)
    f.save(cv_path)
    profil    = parse_cv(cv_path)
    profil_id = save_profil(profil.get("nom","Candidat"), profil.get("email",""), cv_path, profil, user_id=user_id)

    def pipeline():
        mots_cles = profil.get("mots_cles_recherche") or None
        print(f"[Pipeline] {profil.get('nom','?')} — Mots-clés CV : {mots_cles}")
        offres   = run_all_scrapers(mots_cles=mots_cles)
        analyses = run_agent_pipeline(offres, profil)
        save_offres(analyses, profil_id, user_id=user_id)
        envoyer_notification(profil, get_stats(profil_id, user_id=user_id))

    threading.Thread(target=pipeline, daemon=True).start()
    return redirect(url_for("dashboard"))


# ─────────────────────────────────────────────
#  OFFRES
# ─────────────────────────────────────────────

@app.route("/offres")
@login_required
def offres():
    user       = current_user()
    user_id    = user["id"]
    is_admin   = user.get("role") == "admin"
    profil_row = get_latest_profil(user_id=user_id)
    if not profil_row:
        return redirect(url_for("upload"))
    profil_id  = profil_row["id"]
    filtre     = request.args.get("filtre","toutes")
    statut_map = {"pretes":"prêt","candidatees":"candidaté"}
    liste      = get_offres(profil_id, statut=statut_map.get(filtre), user_id=user_id)

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
    {nav('o', is_admin=is_admin, user=user)}
    <div class="container">
      <h1 class="page-title">Offres analysées</h1>
      <div style="display:flex;gap:8px;margin-bottom:24px;">
        <a href="/offres" class="btn {'btn-primary' if filtre=='toutes' else 'btn-ghost'}">Toutes</a>
        <a href="/offres?filtre=pretes" class="btn {'btn-primary' if filtre=='pretes' else 'btn-ghost'}">✅ Prêtes</a>
        <a href="/offres?filtre=candidatees" class="btn {'btn-primary' if filtre=='candidatees' else 'btn-ghost'}">📨 Candidatées</a>
      </div>
      {cards if cards else '<p style="color:var(--muted);text-align:center;padding:60px;">Aucune offre trouvée.</p>'}
    </div></body></html>"""


@app.route("/offre/<int:offre_id>")
@login_required
def detail_offre(offre_id):
    user     = current_user()
    is_admin = user.get("role") == "admin"
    offre    = get_offre(offre_id)
    if not offre:
        return redirect(url_for("offres"))
    sc   = offre["score"]
    tags = "".join(f'<span class="tag">{t.strip()}</span>'
                   for t in (offre.get("match_stack","") or "").split(",") if t.strip())
    lettre = offre.get("lettre_motivation","") or "Lettre non générée (score insuffisant)."

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>{offre['titre']}</title>{BASE_STYLE}</head><body>
    {nav('o', is_admin=is_admin, user=user)}
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
          <div style="display:flex;gap:8px;">
            <button onclick="copyLM()" class="btn btn-ghost" id="copy-btn">Copier</button>
            <a href="/offre/{offre['id']}/pdf" class="btn btn-ghost">📄 Télécharger PDF</a>
          </div>
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
        .then(()=>{{ document.getElementById('copy-btn').textContent='✅ Copié!';
                     setTimeout(()=>document.getElementById('copy-btn').textContent='Copier',2000); }});
    }}
    </script>
    </body></html>"""


@app.route("/offre/<int:offre_id>/pdf")
@login_required
def telecharger_pdf(offre_id):
    user       = current_user()
    offre      = get_offre(offre_id)
    profil_row = get_latest_profil(user_id=user["id"])
    if not offre or not profil_row:
        return redirect(url_for("offres"))

    profil = profil_row["profil_json"]
    nom    = profil.get("nom", "Candidat")
    lettre = offre.get("lettre_motivation", "")
    lettre = nettoyer_lettre_pdf(lettre)
    objet  = f"Candidature alternance — {offre.get('titre','')}"

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    tmp_path = tmp.name

    doc = SimpleDocTemplate(
        tmp_path, pagesize=A4,
        rightMargin=2.5*cm, leftMargin=2.5*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm
    )

    style_nom     = ParagraphStyle("nom",     fontSize=16, fontName="Helvetica-Bold", spaceAfter=4)
    style_contact = ParagraphStyle("contact", fontSize=10, textColor=colors.HexColor("#555555"), spaceAfter=20)
    style_objet   = ParagraphStyle("objet",   fontSize=11, fontName="Helvetica-Bold", spaceAfter=20)
    style_corps   = ParagraphStyle("corps",   fontSize=11, leading=18, alignment=TA_JUSTIFY, spaceAfter=12)

    story = []
    story.append(Paragraph(nom, style_nom))
    story.append(Paragraph(
        f"{profil.get('email','')} · {profil.get('telephone','')} · {profil.get('ecole','')}",
        style_contact
    ))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Objet : {objet}", style_objet))
    story.append(Spacer(1, 0.3*cm))

    for paragraphe in lettre.split("\n\n"):
        if paragraphe.strip():
            story.append(Paragraph(paragraphe.replace("\n", "<br/>"), style_corps))

    doc.build(story)

    with open(tmp_path, "rb") as f:
        pdf_bytes = f.read()

    os.unlink(tmp_path)

    filename = f"LM_{nom.replace(' ','_')}_{offre.get('entreprise','').replace(' ','_')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─────────────────────────────────────────────
#  CANDIDATURES
# ─────────────────────────────────────────────

@app.route("/postuler/<int:offre_id>")
@login_required
def postuler(offre_id):
    user       = current_user()
    user_id    = user["id"]
    profil_row = get_latest_profil(user_id=user_id)
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
    save_candidature(offre_id, profil_id, mode, notes, user_id=user_id)
    return redirect(url_for("detail_offre", offre_id=offre_id))


@app.route("/candidatures")
@login_required
def candidatures():
    user       = current_user()
    user_id    = user["id"]
    is_admin   = user.get("role") == "admin"
    profil_row = get_latest_profil(user_id=user_id)
    if not profil_row:
        return redirect(url_for("upload"))
    liste = get_candidatures(profil_row["id"], user_id=user_id)
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
    {nav('c', is_admin=is_admin, user=user)}
    <div class="container">
      <h1 class="page-title">Candidatures envoyées</h1>
      <p class="page-sub">{len(liste)} candidature(s)</p>
      {cards if cards else '<p style="color:var(--muted);text-align:center;padding:60px;">Aucune candidature encore.</p>'}
    </div></body></html>"""


# ─────────────────────────────────────────────
#  SCAN
# ─────────────────────────────────────────────

@app.route("/run-scan", methods=["POST"])
@login_required
def run_scan():
    user       = current_user()
    user_id    = user["id"]
    profil_row = get_latest_profil(user_id=user_id)
    if not profil_row:
        return jsonify({"error": "Aucun profil — uploadez votre CV d'abord."}), 400

    profil    = profil_row["profil_json"]
    profil_id = profil_row["id"]
    mots_cles = profil.get("mots_cles_recherche") or None
    print(f"[Scan manuel] {profil.get('nom','?')} — keywords: {mots_cles}")

    offres   = run_all_scrapers(mots_cles=mots_cles)
    analyses = run_agent_pipeline(offres, profil)
    nb       = save_offres(analyses, profil_id, user_id=user_id)
    return jsonify({"nb": nb, "total": len(analyses)})


def scan_automatique():
    """Scan quotidien 8h00 — itère sur tous les users actifs avec un CV."""
    print("[Scheduler] Scan automatique lancé...")
    profils = get_all_profils_actifs()

    if not profils:
        print("[Scheduler] Aucun profil actif trouvé.")
        return

    for profil_row in profils:
        profil    = profil_row["profil_json"]
        profil_id = profil_row["id"]
        user_id   = profil_row["user_id"]
        mots_cles = profil.get("mots_cles_recherche") or None

        try:
            print(f"  [Scheduler] {profil.get('nom','?')} (user_id={user_id}) — {len(mots_cles or [])} keywords")
            offres   = run_all_scrapers(mots_cles=mots_cles)
            analyses = run_agent_pipeline(offres, profil)
            nb       = save_offres(analyses, profil_id, user_id=user_id)
            envoyer_notification(profil, get_stats(profil_id, user_id=user_id))
            print(f"  [Scheduler] {profil.get('nom','?')} — {nb} nouvelles offres.")
        except Exception as e:
            print(f"  [Scheduler] Erreur user_id={user_id} : {e}")

    print(f"[Scheduler] Terminé — {len(profils)} user(s) scannés.")


scheduler = BackgroundScheduler()
scheduler.add_job(scan_automatique, 'cron', hour=8, minute=0)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n🚀 LENOUO démarré → http://localhost:5000")
    print("⏰ Scan automatique programmé chaque matin à 8h00\n")
    app.run(debug=False, host="0.0.0.0", port=port)