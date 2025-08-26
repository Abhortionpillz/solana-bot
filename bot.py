import os
import requests
import time
from dotenv import load_dotenv
from telegram import Bot

# Load environment variables (.env for local, Render uses dashboard)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# =============================
# Dexscreener API Endpoint
# =============================
DEX_API = "https://api.dexscreener.com/latest/dex/tokens/solana"

# =============================
# Filters
# =============================
MIN_LIQUIDITY = 30000   # $35k
MIN_FDV = 400000        # $500k
MAX_PAIR_AGE_HOURS = 48 # New pairs only

def fetch_tokens():
    try:
        response = requests.get("https://api.dexscreener.com/latest/dex/search?q=solana", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("pairs", []) or []   # ✅ Always return a list
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print("Error fetching tokens:", e)
        return []

def filter_tokens(pairs):
    gems = []
    for p in pairs:
        liquidity = p.get("liquidity", {}).get("usd", 0)
        fdv = p.get("fdv", 0)
        age = p.get("pairCreatedAt", 0)

        # Convert ms → hours
        hours_old = (time.time()*1000 - age) / (1000*60*60) if age else 999

        if liquidity >= MIN_LIQUIDITY and fdv >= MIN_FDV and hours_old <= MAX_PAIR_AGE_HOURS:
            gems.append(p)
    return gems

def send_alert(token):
    try:
        name = token.get("baseToken", {}).get("name", "Unknown")
        symbol = token.get("baseToken", {}).get("symbol", "")
        url = token.get("url", "https://dexscreener.com/solana")

        msg = f"🚀 New Solana GEM Found!\n\n" \
              f"Name: {name} ({symbol})\n" \
              f"Liquidity: ${token.get('liquidity', {}).get('usd', 0):,.0f}\n" \
              f"FDV: ${token.get('fdv', 0):,.0f}\n" \
              f"Chart: {url}"

        bot.send_message(chat_id=CHAT_ID, text=msg)
        print(f"Sent alert: {name} ({symbol})")
    except Exception as e:
        print("Error sending Telegram alert:", e)

def main():
    print("🚀 Bot started! Scanning Dexscreener every 60s...")
    while True:
        pairs = fetch_tokens()
        gems = filter_tokens(pairs)

        for g in gems:
            send_alert(g)

        time.sleep(600)  # Run every 60 seconds

if __name__ == "__main__":
    main()

