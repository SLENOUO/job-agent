from flask import Blueprint
 
landing = Blueprint('landing', __name__)
 
@landing.route('/home')
def home():
    return LANDING_HTML
 
LANDING_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LENOUO — Ton agent IA de candidature automatique</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
 
    :root {
      --bg: #080c14; --surface: #0f1729; --card: #131d35; --border: #1e2d4a;
      --blue: #3b82f6; --green: #10b981; --amber: #f59e0b; --text: #e2e8f0; --muted: #64748b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: 'Space Grotesk', sans-serif; min-height: 100vh; overflow-x: hidden; }
 
    nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 48px;
          border-bottom: 1px solid var(--border); background: rgba(8,12,20,.95);
          backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; }
    .logo { font-family: 'Space Mono', monospace; font-weight: 700; font-size: 22px; color: var(--blue); letter-spacing: 2px; }
    nav .nav-links { display: flex; gap: 24px; align-items: center; }
    nav a { color: var(--muted); text-decoration: none; font-size: 15px; transition: color .2s; }
    nav a:hover { color: var(--text); }
    .btn-nav { background: var(--blue); color: white !important; padding: 10px 24px; border-radius: 8px; font-weight: 600; font-size: 14px; }
    .btn-nav:hover { background: #2563eb !important; }
    .btn-nav-ghost { border: 1px solid var(--border); color: var(--text) !important; padding: 10px 24px; border-radius: 8px; font-weight: 600; font-size: 14px; }
    .btn-nav-ghost:hover { border-color: var(--green) !important; color: var(--green) !important; }
 
    .hero { text-align: center; padding: 120px 24px 80px; position: relative; overflow: hidden; }
    .hero::before { content: ''; position: absolute; top: -200px; left: 50%; transform: translateX(-50%);
                    width: 800px; height: 800px; background: radial-gradient(circle, rgba(59,130,246,.15) 0%, transparent 70%); pointer-events: none; }
    .badge { display: inline-block; background: rgba(59,130,246,.15); border: 1px solid rgba(59,130,246,.3);
             color: #93c5fd; padding: 6px 16px; border-radius: 999px; font-size: 13px; font-weight: 500; margin-bottom: 24px; }
    .hero h1 { font-size: clamp(36px, 6vw, 72px); font-weight: 700; line-height: 1.1; margin-bottom: 24px;
               max-width: 900px; margin-left: auto; margin-right: auto; }
    .hero h1 span { color: var(--blue); }
    .hero p { font-size: 20px; color: var(--muted); max-width: 600px; margin: 0 auto 48px; line-height: 1.6; }
 
    .hero-cta { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; margin-bottom: 20px; }
    .btn-primary { background: var(--blue); color: white; padding: 16px 36px; border-radius: 12px;
                   font-size: 16px; font-weight: 600; text-decoration: none; transition: all .2s; display: inline-block; }
    .btn-primary:hover { background: #2563eb; transform: translateY(-2px); }
    .btn-trial { background: rgba(16,185,129,.15); color: var(--green); padding: 16px 36px; border-radius: 12px;
                 font-size: 16px; font-weight: 600; text-decoration: none; border: 1px solid rgba(16,185,129,.4);
                 transition: all .2s; display: inline-block; }
    .btn-trial:hover { background: rgba(16,185,129,.25); transform: translateY(-2px); }
    .btn-ghost { background: transparent; color: var(--text); padding: 16px 36px; border-radius: 12px;
                 font-size: 16px; font-weight: 600; text-decoration: none; border: 1px solid var(--border);
                 transition: all .2s; display: inline-block; }
    .btn-ghost:hover { border-color: var(--blue); color: var(--blue); }
 
    .trial-note { color: var(--muted); font-size: 13px; text-align: center; margin-top: 8px; }
    .trial-note span { color: var(--green); font-weight: 600; }
 
    .stats { display: flex; justify-content: center; gap: 64px; padding: 48px 24px;
             border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); flex-wrap: wrap; }
    .stat { text-align: center; }
    .stat .val { font-family: 'Space Mono', monospace; font-size: 42px; font-weight: 700; color: var(--blue); }
    .stat .lbl { color: var(--muted); font-size: 14px; margin-top: 4px; }
 
    .section { padding: 80px 24px; max-width: 1100px; margin: 0 auto; }
    .section-title { text-align: center; font-size: 36px; font-weight: 700; margin-bottom: 12px; }
    .section-sub { text-align: center; color: var(--muted); font-size: 16px; margin-bottom: 56px; }
 
    .steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }
    .step { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 32px 24px; transition: border-color .2s; }
    .step:hover { border-color: var(--blue); }
    .step-num { font-family: 'Space Mono', monospace; font-size: 13px; color: var(--blue); margin-bottom: 16px; font-weight: 700; }
    .step-icon { font-size: 36px; margin-bottom: 16px; }
    .step h3 { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
    .step p { color: var(--muted); font-size: 14px; line-height: 1.6; }
 
    .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
    .feature { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 28px; transition: border-color .2s; }
    .feature:hover { border-color: var(--blue); }
    .feature-icon { font-size: 28px; margin-bottom: 12px; }
    .feature h3 { font-size: 17px; font-weight: 600; margin-bottom: 8px; }
    .feature p { color: var(--muted); font-size: 14px; line-height: 1.6; }
 
    .pricing-wrapper { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; max-width: 780px; margin: 0 auto; }
    .pricing-card { background: var(--card); border: 1px solid var(--border); border-radius: 24px; padding: 40px 36px; text-align: center; position: relative; overflow: hidden; }
    .pricing-card.featured { border: 2px solid var(--blue); }
    .pricing-card.trial-card { border: 2px solid var(--green); }
    .pricing-card::before { content: ''; position: absolute; top: -100px; left: 50%; transform: translateX(-50%);
                             width: 300px; height: 300px; background: radial-gradient(circle, rgba(59,130,246,.08) 0%, transparent 70%); }
    .pricing-card.trial-card::before { background: radial-gradient(circle, rgba(16,185,129,.08) 0%, transparent 70%); }
    .popular-badge { padding: 4px 16px; border-radius: 999px; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 24px; }
    .popular-badge.blue { background: var(--blue); color: white; }
    .popular-badge.green { background: var(--green); color: white; }
    .price { font-family: 'Space Mono', monospace; font-size: 52px; font-weight: 700; color: var(--text); }
    .price span { font-size: 18px; color: var(--muted); }
    .price-sub { color: var(--muted); font-size: 14px; margin: 8px 0 32px; }
    .features-list { text-align: left; margin-bottom: 32px; }
    .features-list li { display: flex; align-items: center; gap: 12px; padding: 10px 0;
                        border-bottom: 1px solid var(--border); font-size: 14px; color: var(--text); list-style: none; }
    .features-list li:last-child { border-bottom: none; }
    .check { color: var(--green); font-size: 16px; }
    .btn-cta { display: block; padding: 16px; border-radius: 12px; font-size: 15px; font-weight: 700; text-decoration: none; transition: all .2s; }
    .btn-cta.blue { background: var(--blue); color: white; }
    .btn-cta.blue:hover { background: #2563eb; transform: translateY(-2px); }
    .btn-cta.green { background: var(--green); color: white; }
    .btn-cta.green:hover { background: #059669; transform: translateY(-2px); }
 
    .faq { max-width: 700px; margin: 0 auto; }
    .faq-item { border-bottom: 1px solid var(--border); padding: 24px 0; }
    .faq-q { font-size: 17px; font-weight: 600; margin-bottom: 12px; }
    .faq-a { color: var(--muted); font-size: 15px; line-height: 1.6; }
 
    footer { text-align: center; padding: 48px 24px; border-top: 1px solid var(--border); color: var(--muted); font-size: 14px; }
    footer .logo-footer { font-family: 'Space Mono', monospace; font-weight: 700; color: var(--blue); font-size: 20px; margin-bottom: 16px; }
  </style>
</head>
<body>
 
<nav>
  <div class="logo">LENOUO</div>
  <div class="nav-links">
    <a href="#fonctionnement">Comment ça marche</a>
    <a href="#tarifs">Tarifs</a>
    <a href="#faq">FAQ</a>
    <a href="/register-trial" class="btn-nav-ghost">Essai gratuit</a>
    <a href="/login" class="btn-nav">Se connecter</a>
  </div>
</nav>
 
<section class="hero">
  <div class="badge">⚡ Agent IA de candidature automatique</div>
  <h1>Trouve et postule aux <span>meilleures offres</span> pendant que tu dors</h1>
  <p>Upload ton CV. L'IA analyse ton profil, scrape les offres, génère des lettres de motivation personnalisées et postule à ta place.</p>
  <div class="hero-cta">
    <a href="/register-trial" class="btn-trial">🎁 Essai gratuit 30 jours →</a>
    <a href="/checkout" class="btn-primary">S'abonner — 8,99€/mois</a>
  </div>
  <p class="trial-note"><span>Sans carte bancaire</span> · Sans engagement · Accès complet pendant 30 jours</p>
</section>
 
<div class="stats">
  <div class="stat"><div class="val">90+</div><div class="lbl">Offres analysées par scan</div></div>
  <div class="stat"><div class="val">3</div><div class="lbl">Plateformes scrappées</div></div>
  <div class="stat"><div class="val">8h</div><div class="lbl">Scan automatique quotidien</div></div>
  <div class="stat"><div class="val">10s</div><div class="lbl">Pour postuler à une offre</div></div>
</div>
 
<section class="section" id="fonctionnement">
  <h2 class="section-title">Comment ça marche</h2>
  <p class="section-sub">3 étapes pour automatiser ta recherche d'emploi</p>
  <div class="steps">
    <div class="step">
      <div class="step-num">01</div>
      <div class="step-icon">📄</div>
      <h3>Upload ton CV</h3>
      <p>L'IA extrait automatiquement ton profil, tes compétences et génère les mots-clés de recherche adaptés à ton domaine.</p>
    </div>
    <div class="step">
      <div class="step-num">02</div>
      <div class="step-icon">🔍</div>
      <h3>L'agent scrape les offres</h3>
      <p>Chaque matin à 8h, l'agent scanne France Travail, Hellowork et d'autres plateformes pour trouver les meilleures opportunités.</p>
    </div>
    <div class="step">
      <div class="step-num">03</div>
      <div class="step-icon">✉️</div>
      <h3>Postule en 1 clic</h3>
      <p>L'IA score chaque offre, génère une lettre de motivation personnalisée et tu postules en 10 secondes.</p>
    </div>
    <div class="step">
      <div class="step-num">04</div>
      <div class="step-icon">📊</div>
      <h3>Suis tes candidatures</h3>
      <p>Dashboard complet pour suivre toutes tes candidatures, télécharger tes LM en PDF et gérer ton pipeline.</p>
    </div>
  </div>
</section>
 
<section style="background:var(--surface);padding:80px 24px;">
  <div style="max-width:1100px;margin:0 auto;">
    <h2 class="section-title">Tout ce dont tu as besoin</h2>
    <p class="section-sub">Un agent IA complet pour ta recherche d'emploi</p>
    <div class="features">
      <div class="feature"><div class="feature-icon">🧠</div><h3>Extraction IA du profil</h3><p>Claude analyse ton CV et extrait automatiquement tes compétences, expériences et génère les mots-clés adaptés à ton domaine.</p></div>
      <div class="feature"><div class="feature-icon">🎯</div><h3>Scoring intelligent</h3><p>Chaque offre reçoit un score de 0 à 10 basé sur le match entre ton profil et les exigences du poste.</p></div>
      <div class="feature"><div class="feature-icon">✍️</div><h3>LM personnalisée par offre</h3><p>Une lettre de motivation unique générée pour chaque offre, basée sur les missions spécifiques et ton parcours.</p></div>
      <div class="feature"><div class="feature-icon">📄</div><h3>Export PDF professionnel</h3><p>Télécharge ta lettre de motivation en PDF prêt à envoyer, avec objet, coordonnées et signature.</p></div>
      <div class="feature"><div class="feature-icon">⏰</div><h3>Scan automatique quotidien</h3><p>L'agent tourne 24h/24 et scanne les nouvelles offres chaque matin à 8h. Tu reçois un email de résumé.</p></div>
      <div class="feature"><div class="feature-icon">🌍</div><h3>Tous domaines</h3><p>Data, finance, marketing, RH, ingénierie... L'agent s'adapte automatiquement à n'importe quel profil.</p></div>
    </div>
  </div>
</section>
 
<section class="section" id="tarifs">
  <h2 class="section-title">Tarif simple et transparent</h2>
  <p class="section-sub">Commence gratuitement, continue si tu aimes</p>
  <div class="pricing-wrapper">
 
    <div class="pricing-card trial-card">
      <div class="popular-badge green">🎁 Essai gratuit</div>
      <div class="price">0€<span>/30j</span></div>
      <div class="price-sub">Sans carte bancaire</div>
      <ul class="features-list">
        <li><span class="check">✓</span> Accès complet 30 jours</li>
        <li><span class="check">✓</span> Analyse IA de ton CV</li>
        <li><span class="check">✓</span> 90+ offres scannées par jour</li>
        <li><span class="check">✓</span> Lettres de motivation personnalisées</li>
        <li><span class="check">✓</span> Export PDF professionnel</li>
        <li><span class="check">✓</span> Dashboard complet</li>
      </ul>
      <a href="/register-trial" class="btn-cta green">Démarrer gratuitement →</a>
      <p style="color:var(--muted);font-size:12px;margin-top:12px;">Aucune CB requise</p>
    </div>
 
    <div class="pricing-card featured">
      <div class="popular-badge blue">⚡ Abonnement</div>
      <div class="price">8,99€<span>/mois</span></div>
      <div class="price-sub">Résiliable à tout moment</div>
      <ul class="features-list">
        <li><span class="check">✓</span> Tout de l'essai gratuit</li>
        <li><span class="check">✓</span> Scan automatique à 8h chaque matin</li>
        <li><span class="check">✓</span> Notifications email quotidiennes</li>
        <li><span class="check">✓</span> Support prioritaire</li>
        <li><span class="check">✓</span> Nouvelles plateformes en continu</li>
        <li><span class="check">✓</span> Accès illimité</li>
      </ul>
      <a href="/checkout" class="btn-cta blue">S'abonner maintenant →</a>
      <p style="color:var(--muted);font-size:12px;margin-top:12px;">Sans engagement · Annulation en 1 clic</p>
    </div>
 
  </div>
</section>
 
<section class="section" id="faq">
  <h2 class="section-title">Questions fréquentes</h2>
  <p class="section-sub">Tout ce que tu dois savoir</p>
  <div class="faq">
    <div class="faq-item">
      <div class="faq-q">L'essai gratuit nécessite-t-il une carte bancaire ?</div>
      <div class="faq-a">Non. L'essai gratuit de 30 jours est accessible sans carte bancaire et sans engagement. Tu crées simplement un compte et tu accèdes à toutes les fonctionnalités.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q">L'agent fonctionne pour tous les domaines ?</div>
      <div class="faq-a">Oui. L'IA analyse ton CV et génère automatiquement les mots-clés adaptés à ton domaine : data, finance, marketing, RH, ingénierie, commerce, etc.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q">Mes données sont-elles sécurisées ?</div>
      <div class="faq-a">Ton CV et tes données sont stockés de façon sécurisée. Nous ne partageons jamais tes informations avec des tiers.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q">Comment l'agent postule-t-il ?</div>
      <div class="faq-a">L'agent fonctionne en mode semi-automatique : il trouve les offres, génère ta lettre de motivation personnalisée, et tu postules en 1 clic depuis le dashboard.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q">Que se passe-t-il après les 30 jours ?</div>
      <div class="faq-a">À la fin de l'essai, tu peux choisir de passer à l'abonnement à 8,99€/mois pour continuer. Si tu ne t'abonnes pas, ton accès se désactive automatiquement.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q">Puis-je annuler à tout moment ?</div>
      <div class="faq-a">Oui, sans engagement et sans frais. Tu peux annuler ton abonnement à tout moment depuis ton compte.</div>
    </div>
  </div>
</section>
 
<section style="text-align:center;padding:80px 24px;background:var(--surface);">
  <h2 style="font-size:36px;font-weight:700;margin-bottom:16px;">Prêt à automatiser ta recherche ?</h2>
  <p style="color:var(--muted);font-size:18px;margin-bottom:40px;">Commence gratuitement, sans carte bancaire</p>
  <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap;">
    <a href="/register-trial" class="btn-trial" style="font-size:17px;padding:18px 44px;">🎁 Essai gratuit 30 jours →</a>
    <a href="/checkout" class="btn-primary" style="font-size:17px;padding:18px 44px;">S'abonner — 8,99€/mois</a>
  </div>
  <p style="color:var(--muted);font-size:13px;margin-top:16px;">Sans CB pour l'essai · Sans engagement pour l'abonnement</p>
</section>
 
<footer>
  <div class="logo-footer">LENOUO</div>
  <p>© 2026 LENOUO. Tous droits réservés.</p>
  <p style="margin-top:8px;">
    <a href="/login" style="color:var(--muted);text-decoration:none;margin:0 12px;">Connexion</a>
    <a href="/register-trial" style="color:var(--muted);text-decoration:none;margin:0 12px;">Essai gratuit</a>
    <a href="/checkout" style="color:var(--muted);text-decoration:none;margin:0 12px;">S'abonner</a>
  </p>
</footer>
 
</body>
</html>"""