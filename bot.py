import os
import time
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, jsonify
from functools import lru_cache
from threading import Lock

# ------------- CONFIG (env) -------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Filters (you can override via Render env vars)
MIN_LIQUIDITY = float(os.getenv("MIN_LIQUIDITY", "35000"))   # USD
MIN_FDV       = float(os.getenv("MIN_FDV", "500000"))        # USD
MAX_AGE_HRS   = float(os.getenv("MAX_AGE_HRS", "24"))        # hours
MIN_TXNS_H1   = int(os.getenv("MIN_TXNS_H1", "300"))         # buys+sells in last 1h
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "60"))        # seconds

# Dexscreener search for Solana
DEX_URL = "https://api.dexscreener.com/latest/dex/search?q=solana"

# ------------- Globals -------------
app = Flask(__name__)
latest_gems = []                 # list of dicts for the dashboard
seen_pairs = set()               # avoid duplicate Telegram alerts
state_lock = Lock()              # protect latest_gems / seen_pairs
started_at = datetime.utcnow()   # service start time


# ------------- Helpers -------------
def send_telegram_message(text: str):
    """Send a Telegram message if token and chat are configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True}
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code >= 400:
            print("❌ Telegram error:", r.text)
        else:
            print("📩 Sent to Telegram:", text[:120] + ("..." if len(text) > 120 else ""))
    except Exception as e:
        print("❌ Telegram exception:", e)


def safe_get(d, path, default=0):
    """Safely get nested keys with defaults."""
    cur = d
    try:
        for k in path:
            cur = cur[k]
        return cur if cur is not None else default
    except Exception:
        return default


def fetch_pairs():
    """Fetch recent pairs for Solana from Dexscreener; always return a list."""
    try:
        res = requests.get(DEX_URL, timeout=15)
        if res.status_code == 200:
            data = res.json() or {}
            return data.get("pairs", []) or []
        else:
            print(f"❌ Dexscreener HTTP {res.status_code}: {res.text[:200]}")
            return []
    except Exception as e:
        print("❌ Fetch error:", e)
        return []


def token_passes_filters(p):
    # numeric fields with safe defaults
    liq = safe_get(p, ["liquidity", "usd"], 0.0) or 0.0
    fdv = float(p.get("fdv") or 0.0)

    # age in hours
    created_ms = p.get("pairCreatedAt") or 0
    if created_ms:
        age_hours = (time.time() * 1000.0 - float(created_ms)) / (1000 * 60 * 60)
    else:
        age_hours = 1e9  # treat unknown age as too old

    # txns last hour
    buys_h1  = safe_get(p, ["txns", "h1", "buys"], 0)
    sells_h1 = safe_get(p, ["txns", "h1", "sells"], 0)
    txns_h1  = int(buys_h1) + int(sells_h1)

    return (
        liq >= MIN_LIQUIDITY and
        fdv >= MIN_FDV and
        age_hours <= MAX_AGE_HRS and
        txns_h1 >= MIN_TXNS_H1
    )


def format_token_msg(p):
    name   = safe_get(p, ["baseToken", "name"], "Unknown")
    symbol = safe_get(p, ["baseToken", "symbol"], "")
    url    = p.get("url", "")
    liq    = safe_get(p, ["liquidity", "usd"], 0.0)
    fdv    = float(p.get("fdv") or 0.0)
    price  = safe_get(p, ["priceUsd"], "N/A")
    buys   = safe_get(p, ["txns", "h1", "buys"], 0)
    sells  = safe_get(p, ["txns", "h1", "sells"], 0)
    created_ms = p.get("pairCreatedAt") or 0
    if created_ms:
        age_hours = (time.time() * 1000.0 - float(created_ms)) / (1000 * 60 * 60)
    else:
        age_hours = None

    age_txt = f"{age_hours:.1f}h" if age_hours is not None else "unknown"
    return (
        "💎 *GEM DETECTED*\n"
        f"Token: {name} ({symbol})\n"
        f"Price: ${price}\n"
        f"Liquidity: ${liq:,.0f} | FDV: ${fdv:,.0f}\n"
        f"1h Trades: {int(buys)+int(sells)} (B:{buys}/S:{sells})\n"
        f"Age: {age_txt}\n"
        f"Chart: {url}"
    )


def scan_once():
    """One scan cycle: fetch → filter → update state → alert new ones."""
    pairs = fetch_pairs()
    print(f"🔎 Fetched {len(pairs)} pairs")

    found = []
    for p in pairs:
        try:
            if token_passes_filters(p):
                found.append(p)
        except Exception as e:
            # Never let one bad record break the scan
            print("⚠️ Filter exception:", e)

    # Update globals safely; send alerts only for new pair addresses
    new_alerts = []
    with state_lock:
        # keep last 25 gems for dashboard
        # also dedupe telegram alerts by pair address
        pair_ids = []
        updated_list = []

        for g in found:
            pair_addr = g.get("pairAddress") or g.get("url") or repr(g)
            pair_ids.append(pair_addr)
            updated_list.append(g)
            if pair_addr not in seen_pairs:
                seen_pairs.add(pair_addr)
                new_alerts.append(g)

        # update dashboard list
        global latest_gems
        # put most recent first; cap size
        latest_gems = updated_list[:25]

    # Send alerts after releasing lock
    for g in new_alerts:
        send_telegram_message(format_token_msg(g))

    print(f"✅ {len(found)} passed filters | {len(new_alerts)} new alerts")


def bot_loop():
    """Continuous loop."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        send_telegram_message("🚀 Bot is live and scanning…")

    while True:
        try:
            scan_once()
        except Exception as e:
            print("❌ Scan cycle exception:", e)
        time.sleep(SCAN_INTERVAL)


# ------------- Flask routes -------------
@app.route("/")
def home():
    # Auto-refresh in the template
    with state_lock:
        gems_copy = list(latest_gems)
    return render_template(
        "index.html",
        gems=gems_copy,
        started=str(started_at) + " UTC",
        filters=dict(
            MIN_LIQUIDITY=MIN_LIQUIDITY,
            MIN_FDV=MIN_FDV,
            MAX_AGE_HRS=MAX_AGE_HRS,
            MIN_TXNS_H1=MIN_TXNS_H1,
            SCAN_INTERVAL=SCAN_INTERVAL,
        ),
    )

@app.route("/health")
def health():
    return jsonify(ok=True, uptime_seconds=int((datetime.utcnow() - started_at).total_seconds()))

@app.route("/force-scan")
def force_scan():
    # Quick manual trigger from your browser if you want
    try:
        scan_once()
        return jsonify(ok=True, message="Scan triggered")
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


# ------------- Entrypoint -------------
def start_flask():
    port = int(os.environ.get("PORT", "8080"))  # Render supplies PORT
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Run Flask (web) and bot loop (scanner) together
    threading.Thread(target=start_flask, daemon=True).start()
    bot_loop()
