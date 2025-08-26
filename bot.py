from flask import Flask, render_template
import threading
import time
import requests
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)

latest_gems = []  # store last found tokens


def send_telegram_message(text):
    """Send message to Telegram chat"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
        print("📩 Sent to Telegram:", text)
    except Exception as e:
        print("❌ Telegram error:", e)


def fetch_tokens():
    url = "https://api.dexscreener.com/latest/dex/tokens"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json().get("pairs", [])
    except Exception as e:
        print("Error fetching:", e)
    return []


def filter_tokens(pairs):
    gems = []
    for p in pairs:
        try:
            liquidity = p.get("liquidity", {}).get("usd", 0)
            fdv = p.get("fdv", 0)
            txns = p.get("txns", {}).get("h1", {}).get("buys", 0) + p.get("txns", {}).get("h1", {}).get("sells", 0)

            if liquidity > 25000 and fdv > 300000 and txns > 200:
                gems.append(p)
        except:
            continue
    return gems


def bot_loop():
    global latest_gems
    while True:
        pairs = fetch_tokens()
        if pairs:
            gems = filter_tokens(pairs)
            if gems:
                latest_gems = gems  # update global gems
                gem_symbols = [g["baseToken"]["symbol"] for g in gems]
                msg = f"🚀 New Gems Found:\n" + "\n".join(gem_symbols)
                print("✅ Found Gems:", gem_symbols)
                send_telegram_message(msg)
        time.sleep(60)


@app.route("/")
def home():
    return render_template("index.html", gems=latest_gems)


def start_flask():
    app.run(host="0.0.0.0", port=10000)


if __name__ == "__main__":
    threading.Thread(target=start_flask).start()
    bot_loop()

