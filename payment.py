import stripe
import os
from flask import Blueprint, redirect, request, url_for, session
from database import get_user_by_id, toggle_user_actif

payment = Blueprint('payment', __name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_PRICE_ID   = os.getenv("STRIPE_PRICE_ID", "")
DOMAIN            = os.getenv("DOMAIN", "http://localhost:5000")


@payment.route("/checkout")
def checkout():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    if not user:
        return redirect(url_for("login"))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=DOMAIN + "/payment/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=DOMAIN + "/payment/cancel",
            customer_email=user["email"],
            metadata={"user_id": str(user["id"])},
        )
        return redirect(checkout_session.url)
    except Exception as e:
        return f"Erreur Stripe: {e}", 400


@payment.route("/payment/success")
def payment_success():
    return """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Paiement réussi</title>
    <style>
      body { background:#080c14; color:#e2e8f0; font-family:'DM Sans',sans-serif;
             display:flex; align-items:center; justify-content:center; min-height:100vh; }
      .box { text-align:center; background:#131d35; border:1px solid #1e2d4a;
             border-radius:16px; padding:48px; max-width:400px; }
      h1 { color:#10b981; font-size:28px; margin-bottom:16px; }
      p { color:#64748b; margin-bottom:24px; }
      a { background:#3b82f6; color:white; padding:12px 24px; border-radius:8px;
          text-decoration:none; font-weight:600; }
    </style></head><body>
    <div class="box">
      <div style="font-size:64px;">🎉</div>
      <h1>Paiement réussi !</h1>
      <p>Ton abonnement LENOUO Premium est activé. Upload ton CV pour commencer.</p>
      <a href="/upload">Commencer →</a>
    </div></body></html>"""


@payment.route("/payment/cancel")
def payment_cancel():
    return """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
    <title>Paiement annulé</title>
    <style>
      body { background:#080c14; color:#e2e8f0; font-family:'DM Sans',sans-serif;
             display:flex; align-items:center; justify-content:center; min-height:100vh; }
      .box { text-align:center; background:#131d35; border:1px solid #1e2d4a;
             border-radius:16px; padding:48px; max-width:400px; }
      h1 { color:#ef4444; font-size:28px; margin-bottom:16px; }
      p { color:#64748b; margin-bottom:24px; }
      a { background:#3b82f6; color:white; padding:12px 24px; border-radius:8px;
          text-decoration:none; font-weight:600; }
    </style></head><body>
    <div class="box">
      <div style="font-size:64px;">😕</div>
      <h1>Paiement annulé</h1>
      <p>Tu peux réessayer quand tu veux.</p>
      <a href="/home">Retour →</a>
    </div></body></html>"""