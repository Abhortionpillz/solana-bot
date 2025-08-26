from flask import Flask, render_template
import threading
import time
import requests
import os
from dotenv import load_dotenv
from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "🚀 Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Load env vars
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("⚠️ Telegram not configured.")
    exit(1)  # stop program if not configured

app = Flask(__name__)

latest_gems = []  # store last found tokens


def send_telegram_message(text):
    """Send message to Telegram chat"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
    if not pairs:
        return gems

    print("📊 Debug: Fetched tokens =", len(pairs))  # 👈 print count

    for p in pairs:
        try:
            liquidity = float(p['liquidity']['usd'])
            fdv = float(p['fdv'])
            age = int(p['pairCreatedAt'])  # milliseconds timestamp
            trades = int(p['txns']['h1']['buys']) + int(p['txns']['h1']['sells'])

            # Debug: print basic info
            print(f"Token {p['baseToken']['symbol']} | Liquidity={liquidity}, FDV={fdv}, Trades={trades}")

            # Your filter rules
            if liquidity > 20000 and fdv > 100000 and trades > 100:
                gems.append(p)
        except Exception as e:
            print("⚠️ Error parsing token:", e)
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
    send_telegram_message("🚀 Test: Your bot is connected successfully!")

import time
import requests
import os

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)
    print(f"📩 Sent to Telegram: {text}")

# Send test message on startup
send_telegram_message("🚀 Bot started and is running!")

# Keep the bot alive with a loop
while True:
    send_telegram_message("⏰ Still alive and running...")
    time.sleep(600)  # wait 10 minute
    

