 # app/ws/birdeye_price_ws.py
import os
import json
import time
import datetime as dt
import threading
from pathlib import Path

import websocket  # pip install websocket-client
import requests

from app.io.ticks_writer import write_tick

TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}

# --- config from env ---
API_KEY = os.getenv("BIRDEYE_API_KEY", "").strip()
OUT_DIR = os.getenv("TICKS_OUT_DIR", "data/real/ticks")
WS_URL  = f"wss://public-api.birdeye.so/socket/solana?x-api-key={API_KEY}"

# Birdeye v3 OHLCV (used only for optional sanity checks)
OHLCV_V3 = "https://public-api.birdeye.so/defi/v3/ohlcv"

# guard: show config once
print(f"[cfg] out_dir = {OUT_DIR}")
print(f"[cfg] tokens  = {TOKENS}")
print(f"[cfg] ws_url  = wss://public-api.birdeye.so/socket/solana?x-api-key={'<hidden>' if API_KEY else '<missing>'}")

if not API_KEY:
    raise SystemExit("BIRDEYE_API_KEY missing")

Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

addr_to_sym = {v: k for k, v in TOKENS.items()}
last_min_written = {sym: None for sym in TOKENS}

def unix_to_iso_z(t: int) -> str:
    # timezone-aware (UTC) → ISO Z
    return dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")

def build_complex_query(addresses):
    # (address = <mint> AND chartType = 1m AND currency = usd) OR ...
    parts = [f"(address = {a} AND chartType = 1m AND currency = usd)" for a in addresses]
    return " OR ".join(parts)

def send_subscribe_all(ws):
    # One complex subscription covering all token addresses
    q = build_complex_query(list(TOKENS.values()))
    msg = {
        "type": "SUBSCRIBE_PRICE",
        "data": {
            "queryType": "complex",
            "query": q
        }
    }
    ws.send(json.dumps(msg))
    print("[ws] sent complex SUBSCRIBE_PRICE for:", ", ".join(f"{s}->{a}" for s, a in TOKENS.items()))

def on_open(ws):
    print("Websocket connected")
    send_subscribe_all(ws)

def on_message(ws, message):
    try:
        obj = json.loads(message)
    except Exception:
        return

    typ = obj.get("type")
    data = obj.get("data")

    if typ == "WELCOME":
        print("[msg-type] WELCOME")
        return

    if typ == "ERROR":
        print(f"[msg-type] ERROR {data}")
        return

    if typ == "PRICE_DATA" and isinstance(data, dict):
        addr = data.get("address")
        c    = data.get("c")
        unix = data.get("unixTime")
        if addr not in addr_to_sym or c is None or unix is None:
            return

        sym = addr_to_sym[addr]
        ts_iso = unix_to_iso_z(int(unix))
        minute_key = ts_iso[:16]  # YYYY-MM-DDTHH:MM

        # de-dupe per minute per symbol
        if last_min_written.get(sym) == minute_key:
            return
        last_min_written[sym] = minute_key

        # write
        write_tick(OUT_DIR, sym, ts_iso, float(c))
        print(f"[write-ws] {sym:4s} {ts_iso} {c}")

def on_error(ws, err):
    print("[ws-error]", err)

def on_close(ws, code, reason):
    print("[ws-close]", code, reason)

def run_ws():
    headers = [
        "Origin: https://birdeye.so",
        f"X-API-KEY: {API_KEY}",
        "Sec-WebSocket-Protocol: echo-protocol",
    ]
    websocket.enableTrace(False)  # set True if you want raw frames again
    ws = websocket.WebSocketApp(
        WS_URL,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    # keepalive every 30s
    ws.run_forever(ping_interval=30, ping_payload="keepalive")

# ---- optional: tiny sanity pinger for any stale symbol (uses v3 OHLCV) ----
def sanity_check_once(sym: str, addr: str, stale_minutes: int = 5):
    # If last write is stale, fetch last 1m candle from OHLCV v3 and write it.
    # Keeps you from getting "stuck" if WS lags for a specific token.
    now = int(time.time())
    params = {
        "address": addr,
        "time_from": now - 3600,   # last hour
        "time_to": now,
        "type_in_time": "1m",
    }
    try:
        r = requests.get(
            OHLCV_V3,
            params=params,
            headers={"X-API-KEY": API_KEY, "x-chain": "solana"},
            timeout=10,
        )
        r.raise_for_status()
        payload = r.json()
        candles = payload.get("data") or []
        if not candles:
            return
        # v3 returns list of dicts with unixTime & c
        last = candles[-1]
        close = float(last["c"])
        ts_iso = unix_to_iso_z(int(last["unixTime"]))
        # only write if our file is stale beyond threshold
        lm = last_min_written.get(sym)
        if lm is None or lm < ts_iso[:16]:
            write_tick(OUT_DIR, sym, ts_iso, close)
            last_min_written[sym] = ts_iso[:16]
            print(f"[write-rest] {sym:4s} {ts_iso} {close}")
    except Exception as e:
        print(f"[rest-error] {sym} {e}")

def sanity_loop():
    while True:
        # poke only if we haven't written for a while
        for sym, addr in TOKENS.items():
            sanity_check_once(sym, addr, stale_minutes=5)
        time.sleep(60)

def main():
    # run ws in main thread, sanity checker in background
    t = threading.Thread(target=sanity_loop, daemon=True)
    t.start()
    # backoff reconnect loop
    backoff = 2
    while True:
        try:
            run_ws()
            backoff = 2
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("[ws-run] exception:", e)
            time.sleep(backoff)
            backoff = min(60, backoff * 2)

if __name__ == "__main__":
    main()



