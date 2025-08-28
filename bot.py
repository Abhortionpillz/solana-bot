import os
import time
import requests
import threading
from flask import Flask
from dotenv import load_dotenv

from flask import Flask, render_template

# Example filters (replace with your real filter config)
class Filters:
    MIN_LIQUIDITY = 50000
    MAX_MC = 100000
    MIN_HOLDERS = 100

filters = Filters()

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", filters=filters)  # <-- pass filters

# Load environment variables
load_dotenv()

# --- Config ---
BITQUERY_URL = "https://graphql.bitquery.io"
BITQUERY_KEY = os.getenv("BITQUERY_API_KEY")   # get from https://bitquery.io
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Dexscreener API for Solana new pairs
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/solana"

# --- Flask App (keeps Render alive) ---
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", filters=filters)  # <-- pass filters
    
# --- Telegram Helper ---
def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"📩 Sent: {msg[:50]}...")
    except Exception as e:
        print(f"❌ Telegram error: {e}")
while True:
    send_telegram_message("⏰ Still alive and running...")
    time.sleep(300)  # wait 5 minute
# --- Pump.fun Query ---
def get_new_tokens_pumpfun():
    query = """
    {
      Solana {
        TokenSupplyUpdates(
          limit: {count: 5}
          orderBy: {descending: Block_Time}
          where: {
            Instruction: {
              Program: {Name: {is: "pump"}}
            }
          }
        ) {
          TokenSupplyUpdate {
            Currency {
              MintAddress
              Name
              Symbol
            }
          }
          Block {
            Time
          }
        }
      }
    }
    """
    headers = {"X-API-KEY": BITQUERY_KEY}
    try:
        resp = requests.post(BITQUERY_URL, json={"query": query}, headers=headers, timeout=15)
        data = resp.json()
        return data.get("data", {}).get("Solana", {}).get("TokenSupplyUpdates", [])
    except Exception as e:
        print(f"❌ Pump.fun error: {e}")
        return []

# --- Dexscreener New Pairs ---
def get_new_tokens_dexscreener():
    try:
        resp = requests.get(DEXSCREENER_URL, timeout=15)
        data = resp.json()
        pairs = data.get("pairs", [])[:10]  # check latest 10
        return pairs
    except Exception as e:
        print(f"❌ Dexscreener error: {e}")
        return []

# --- Background Worker ---
def worker():
    seen_pump = set()
    seen_dex = set()

    while True:
        # Pump.fun
        tokens_pump = get_new_tokens_pumpfun()
        for t in tokens_pump:
            mint = t["TokenSupplyUpdate"]["Currency"]["MintAddress"]
            name = t["TokenSupplyUpdate"]["Currency"].get("Name", "")
            symb = t["TokenSupplyUpdate"]["Currency"].get("Symbol", "")
            time_block = t["Block"]["Time"]

            # Filter: must have name, symbol, and valid mint
            if mint and name and symb and mint not in seen_pump:
                seen_pump.add(mint)
                msg = (
                    f"🔥 Pump.fun New Token!\n\n"
                    f"Name: {name}\n"
                    f"Symbol: {symb}\n"
                    f"Mint: {mint}\n"
                    f"Time: {time_block}"
                )
                send_telegram(msg)

        # Dexscreener
        tokens_dex = get_new_tokens_dexscreener()
        for pair in tokens_dex:
            address = pair.get("baseToken", {}).get("address")
            name = pair.get("baseToken", {}).get("name", "")
            symb = pair.get("baseToken", {}).get("symbol", "")
            dex_url = pair.get("url", "")

            liquidity_usd = pair.get("liquidity", {}).get("usd", 0)
            fdv = pair.get("fdv", 0)

            # Filter: liquidity ≥ $5k and FDV ≥ $10k
            if (
                address
                and liquidity_usd >= 5000
                and fdv >= 10000
                and address not in seen_dex
            ):
                seen_dex.add(address)
                msg = (
                    f"⚡ DexScreener New Pair!\n\n"
                    f"Name: {name}\n"
                    f"Symbol: {symb}\n"
                    f"Liquidity: ${liquidity_usd:,.0f}\n"
                    f"FDV: ${fdv:,.0f}\n"
                    f"Address: {address}\n"
                    f"Chart: {dex_url}"
                )
                send_telegram(msg)

        time.sleep(60)  # refresh every 60s

# --- Start worker in background thread ---
threading.Thread(target=worker, daemon=True).start()



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
