import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config import EMAIL_SENDER, EMAIL_PASSWORD, SMTP_HOST, SMTP_PORT


def envoyer_candidature(offre: dict, profil: dict, cv_path: str) -> bool:
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("[Mailer] Credentials email manquants dans .env")
        return False

    destinataire = offre.get("email_contact", "")
    if not destinataire:
        print(f"[Mailer] Pas d'email de contact pour {offre.get('titre')}")
        return False

    nom        = profil.get("nom", "Le candidat")
    lettre     = offre.get("lettre_motivation", "")

    msg = MIMEMultipart()
    msg["From"]    = f"{nom} <{EMAIL_SENDER}>"
    msg["To"]      = destinataire
    msg["Subject"] = f"Candidature alternance – {offre.get('titre','')} | {nom}"

    corps_html = f"""
    <html><body style="font-family:Arial,sans-serif;font-size:14px;line-height:1.7;">
        <p>{lettre.replace(chr(10), '<br>')}</p>
        <br>
        <p style="color:#666;font-size:12px;">
            CV joint en pièce jointe.<br>
            {nom} — {profil.get('email','')} — {profil.get('telephone','')}
        </p>
    </body></html>
    """
    msg.attach(MIMEText(corps_html, "html", "utf-8"))

    if cv_path and os.path.exists(cv_path):
        with open(cv_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=CV_{nom.replace(' ','_')}.pdf")
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, destinataire, msg.as_string())
        print(f"[Mailer] ✅ Email envoyé → {destinataire}")
        return True
    except Exception as e:
        print(f"[Mailer] ❌ Erreur: {e}")
        return False


def envoyer_notification(profil: dict, stats: dict) -> bool:
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return False

    destinataire = profil.get("email", "")
    if not destinataire:
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = destinataire
    msg["Subject"] = f"🎯 Agent Job — {stats.get('pretes', 0)} candidature(s) prête(s)"

    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#0f172a;color:#f1f5f9;padding:32px;">
        <h2 style="color:#3b82f6;">🤖 Rapport de ton agent</h2>
        <div style="background:#1e293b;border-radius:12px;padding:24px;margin:16px 0;">
            <p>📊 <strong>{stats.get('total',0)}</strong> offres analysées</p>
            <p>✅ <strong>{stats.get('pretes',0)}</strong> candidatures prêtes</p>
            <p>📨 <strong>{stats.get('envoyes',0)}</strong> candidatures envoyées</p>
            <p>🏆 Meilleur score : <strong>{stats.get('top_score',0)}/10</strong></p>
        </div>
        <a href="http://localhost:5000" style="background:#3b82f6;color:white;padding:12px 24px;
           border-radius:8px;text-decoration:none;font-weight:bold;">
            Ouvrir le dashboard →
        </a>
    </body></html>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, destinataire, msg.as_string())
        return True
    except Exception as e:
        print(f"[Mailer] Notif erreur: {e}")
        return False