from flask import Flask, render_template
import threading
import time
import requests

app = Flask(__name__)

latest_gems = []  # store last found tokens

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
            if liquidity > 35000 and fdv > 500000 and txns > 300:
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
                print("✅ Found Gems:", [g["baseToken"]["symbol"] for g in gems])
        time.sleep(60)

@app.route("/")
def home():
    return render_template("index.html", gems=latest_gems)

def start_flask():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    threading.Thread(target=start_flask).start()
    bot_loop()

