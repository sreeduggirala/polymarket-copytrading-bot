import os
import json
import time
import asyncio
from typing import Dict, List
import requests

from utils.telegram import send_markdown

# === config ===
tracked_wallets: Dict[str, str] = {
    "0x751a2b86cab503496efd325c8344e10159349ea1": "Sharky6999",
    "0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292": "Dropper",
    "0x44c1dfe43260c94ed4f1d00de2e1f80fb113ebc1": "tomatosauce",
    "0xd218e474776403a330142299f7796e8ba32eb5c9": "cigarettes",
    "0x6ffb4354cbe6e0f9989e3b55564ec5fb8646a834": "AgricultureSecretary",
    "0xd189664c5308903476f9f079820431e4fd7d06f4": "rwo",
    "0xa9b44dca52ed35e59ac2a6f49d1203b8155464ed": "VvVv",
}

DATA_API = "https://data-api.polymarket.com"
POLL_INTERVAL = 2.0  # seconds between full sweeps
PAGE_LIMIT = 250     # 250–500 is fine
REPLAY_WINDOW_SEC = 180  # small rewind at boot to avoid edge misses

# === http session ===
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

# === persistence (timestamp-only) ===
TS_FILE = ".last_ts.json"  # { wallet_lower: last_ts_int }
last_ts: Dict[str, int] = {}

# in-memory dedupe for trades that share the same timestamp as last_ts
# wallet_lower -> set(txhash)
same_ts_seen: Dict[str, set] = {}


def _lower_dict(d: Dict[str, str]) -> Dict[str, str]:
    return {k.lower(): v for k, v in d.items()}


def load_last_ts(path: str = TS_FILE) -> None:
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                raw = json.load(f)
            for w, ts in raw.items():
                if isinstance(ts, int):
                    last_ts[w] = ts
    except Exception as e:
        print(f"[cursor] load error: {e}")


def save_last_ts(path: str = TS_FILE) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(last_ts, f)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[cursor] save error: {e}")


def fetch_user_trades(wallet: str, limit: int = PAGE_LIMIT, offset: int = 0) -> List[dict]:
    r = SESSION.get(
        f"{DATA_API}/trades",
        params={"user": wallet, "limit": limit, "offset": offset},
        timeout=8,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("trades", []) or []


def format_trade_msg(t: dict, name: str) -> str:
    token_id = t["asset"]
    side = t["side"]
    size = float(t["size"])
    price = float(t["price"])
    timestamp = int(t["timestamp"])
    tx = t.get("transactionHash", "") or ""
    outcome = t.get("outcome") or ""
    title = t.get("title") or t.get("slug") or ""
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(timestamp))
    return (
        f"*{name}* — *{side}* {size} @ {price}\n"
        f"`{outcome}` — {title}\n"
        f"`token_id:` `{token_id}`\n"
        f"`tx:` `{tx}`\n"
        f"{ts_str} UTC"
    )


def bootstrap_ts(wallets: Dict[str, str], rewind_sec: int = REPLAY_WINDOW_SEC) -> None:
    print(f"BOOT wallets={list(wallets.keys())}")
    now = int(time.time())
    default_ts = now - rewind_sec
    for w in wallets:
        w_l = w.lower()
        if w_l not in last_ts:
            # If we’ve never seen this wallet, start slightly in the past
            last_ts[w_l] = default_ts
        same_ts_seen.setdefault(w_l, set())
        print(f"BOOT last_ts[{w_l}]={last_ts[w_l]}")


def main():
    wallets = _lower_dict(tracked_wallets)

    load_last_ts()
    bootstrap_ts(wallets)

    try:
        while True:
            sweep_start = time.time()

            for wallet, name in wallets.items():
                try:
                    tip = fetch_user_trades(wallet, limit=PAGE_LIMIT, offset=0)
                    if not tip:
                        print(f"[poll] {wallet} empty page")
                        continue

                    # Oldest → newest so we don’t miss sequences
                    tip.sort(key=lambda t: int(t.get("timestamp", 0)))

                    ts_cut = last_ts.get(wallet, 0)
                    seen = same_ts_seen.setdefault(wallet, set())

                    new_items = []
                    for t in tip:
                        ts = int(t.get("timestamp", 0))
                        tx = t.get("transactionHash", "") or ""
                        if ts > ts_cut:
                            new_items.append(t)
                        elif ts == ts_cut and tx not in seen:
                            # same second as cursor; avoid dupes using an in-memory set
                            new_items.append(t)

                    if not new_items:
                        print(f"[poll] {wallet} no new (cursor={ts_cut}, page_tip_ts={int(tip[-1].get('timestamp',0))})")
                        continue

                    # Emit from oldest to newest
                    for t in new_items:
                        asyncio.run(send_markdown(format_trade_msg(t, name)))
                        ts = int(t.get("timestamp", 0))
                        tx = t.get("transactionHash", "") or ""

                        # advance timestamp & maintain the in-memory set
                        if ts > ts_cut:
                            last_ts[wallet] = ts
                            ts_cut = ts
                            seen.clear()  # new second -> reset dedupe
                        if ts == ts_cut:
                            seen.add(tx)

                    save_last_ts()

                except Exception as e:
                    print(f"[loop] {wallet} error: {e}")

            elapsed = time.time() - sweep_start
            time.sleep(max(0.1, POLL_INTERVAL - elapsed + 0.05))
    finally:
        save_last_ts()


if __name__ == "__main__":
    main()
