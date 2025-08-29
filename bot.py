import os
import time
import requests
import logging
import telegram
from flask import Flask, render_template

# Example filters (replace with your real filter config)

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", filters=filters) 

# ================== CONFIG ==================
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/pairs/solana"
CHECK_INTERVAL = 60  # seconds between checks
NEW_TOKEN_MAX_AGE = 300  # 5 minutes (tokens listed in last 5 minutes)

# Telegram Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # add in Render Dashboard
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # your chat ID

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise Exception("⚠️ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in environment!")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Track seen pairs to avoid duplicates
seen_tokens = set()

# ================== MAIN LOOP ==================
def fetch_new_sol_tokens():
    try:
        response = requests.get(DEXSCREENER_API, timeout=10)
        data = response.json()

        if "pairs" not in data:
            return []

        new_tokens = []
        for pair in data["pairs"]:
            base_token = pair.get("baseToken", {})
            token_address = base_token.get("address")
            token_name = base_token.get("name", "Unknown")
            token_symbol = base_token.get("symbol", "???")
            created_at = pair.get("pairCreatedAt", 0)

            # Only alert if token is brand new
            age_seconds = (time.time() * 1000 - created_at) / 1000
            if token_address and token_address not in seen_tokens and age_seconds < NEW_TOKEN_MAX_AGE:
                seen_tokens.add(token_address)
                new_tokens.append({
                    "name": token_name,
                    "symbol": token_symbol,
                    "address": token_address,
                    "age": int(age_seconds),
                    "url": f"https://dexscreener.com/solana/{token_address}"
                })
        return new_tokens

    except Exception as e:
        logging.error(f"Error fetching Dexscreener: {e}")
        return []

def send_telegram_alert(token):
    msg = (
        f"🚀 New Solana MemeCoin Listed!\n\n"
        f"🪙 {token['name']} ({token['symbol']})\n"
        f"⏱ Age: {token['age']} sec\n"
        f"🔗 [View on Dexscreener]({token['url']})"
    )
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")
        logging.info(f"📩 Sent alert for {token['symbol']}")
    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")

def main():
    logging.info("🚀 Bot started. Watching for new Solana tokens...")
    while True:
        new_tokens = fetch_new_sol_tokens()
        for token in new_tokens:
            send_telegram_alert(token)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
