"""
WooCommerce Dashboard Agent - Backend API
============================================
Ye Flask server chat widget (wp-chat-widget.html) aur Agno agent (woo_agent.py
ke tools) ke darmiyan bridge ka kaam karta hai.

SETUP:
1. pip install -r requirements.txt flask flask-cors
2. .env file (woo_agent.py wali hi) isi folder mein honi chahiye
3. Run: python woo_agent_api.py
   Default: http://0.0.0.0:5000

DEPLOYMENT NOTE:
Isay apne WordPress site ke saath ek subdomain/port par host karein
(e.g. gunicorn/systemd se). Phir wp-chat-widget.html mein API_URL
usi address par point karein. Production mein CORS ko sirf apni
domain tak restrict karein (neeche CORS() call dekhein).
"""

import os
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from woo_agent import woo_agent, _woo_get  # reuse tools/agent from woo_agent.py

app = Flask(__name__)


# ---------------------------------------------------------------------------
# PWA static files (phone "app" version) - isi folder se serve hote hain
# ---------------------------------------------------------------------------
@app.route("/")
def pwa_index():
    return send_from_directory(".", "pwa_index.html")


@app.route("/manifest.json")
def pwa_manifest():
    return send_from_directory(".", "manifest.json")


@app.route("/sw.js")
def pwa_sw():
    return send_from_directory(".", "sw.js")


@app.route("/icon-192.png")
def pwa_icon_192():
    return send_from_directory(".", "icon-192.png")


@app.route("/icon-512.png")
def pwa_icon_512():
    return send_from_directory(".", "icon-512.png")


# Production mein "*" ki jagah apni WordPress domain likhein:
# CORS(app, origins=["https://yourstore.com"])
CORS(app, origins=["*"])


@app.route("/api/chat", methods=["POST"])
def chat():
    # --- Security check: sirf sahi APP_SECRET wale requests allow karein ---
    provided_secret = request.headers.get("X-App-Secret", "")
    expected_secret = os.getenv("APP_SECRET", "")
    if not expected_secret or provided_secret != expected_secret:
        return jsonify({"reply": "Unauthorized."}), 401

    body = request.get_json(force=True, silent=True) or {}
    message = body.get("message", "").strip()

    if not message:
        return jsonify({"reply": "Message khali nahi ho sakta."}), 400

    # Widget har 60 second mein header ticker refresh karta hai -
    # is special message ka jawab tool result se seedha nikal ke dete hain
    # (agent ko call kiye baghair, taake tez ho aur token na jaye)
    if message == "__TICKER__":
        try:
            today_start = datetime.utcnow().strftime("%Y-%m-%dT00:00:00")
            _, headers = _woo_get("orders", {"after": today_start, "per_page": 1, "status": "any"})
            orders_today = headers.get("X-WP-Total", "0")

            since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
            data, _ = _woo_get("orders", {"after": since, "per_page": 100, "status": "any"})
            sales_7d = sum(float(o["total"]) for o in data)

            return jsonify({
                "orders_today": orders_today,
                "sales_7d": f"{sales_7d:,.0f}",
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        run = woo_agent.run(message)
        reply = run.content if hasattr(run, "content") else str(run)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": f"Error aya: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
