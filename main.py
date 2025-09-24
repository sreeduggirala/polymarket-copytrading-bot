# main.py (sync)
import time
import asyncio
from typing import Dict, Tuple
import requests

from utils.polymarket import get_market_price, create_order, tracked_wallets
from utils.telegram import send_markdown

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

DATA_API = "https://data-api.polymarket.com"
POLL_INTERVAL = 2.0  # seconds

# wallet -> (timestamp, txhash)
LastPtr = Tuple[int, str]
last_seen: Dict[str, LastPtr] = {}


def fetch_user_trades(wallet: str, limit: int = 50):
    r = SESSION.get(
        f"{DATA_API}/trades", params={"user": wallet, "limit": limit}, timeout=6
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("trades", [])


def ptr_of(t: dict) -> LastPtr:
    return (int(t.get("timestamp", 0)), t.get("transactionHash", "") or "")


def bootstrap_from_api():
    for w in (
        tracked_wallets if isinstance(tracked_wallets, list) else tracked_wallets.keys()
    ):
        trades = fetch_user_trades(w, limit=1)
        if trades:
            last_seen[w] = ptr_of(trades[0])
        else:
            last_seen[w] = (int(time.time()), "")


def notify_sync_copied(t: dict, name: str):
    token_id = t["asset"]
    side = t["side"]
    size = float(t["size"])
    ref_price = float(t["price"])
    timestamp = int(t["timestamp"])
    tx = t.get("transactionHash", "") or ""
    msg = (
        f"*Copied Trade*\n"
        f"{name} — {side} {size} @ {ref_price}\n"
        f"`token_id:` `{token_id}`\n"
        f"`tx:` `{tx}`\n"
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))} UTC"
    )
    asyncio.run(send_markdown(msg))


def handle_trade_sync(t: dict) -> bool:
    """Return True if order placed, else False."""
    try:
        token_id = t["asset"]
        side = t["side"]
        size = float(t["size"])

        # Use the REST price endpoint directly with requests for sync flow
        r = SESSION.get(
            "https://clob.polymarket.com/price",
            params={"token_id": token_id, "side": side},
            timeout=6,
        )
        r.raise_for_status()
        market_price = float(r.json()["price"])

        resp = create_order(price=market_price, size=size, side=side, token_id=token_id)
        return bool(resp)
    except Exception as e:
        print(f"[handle_trade_sync] Error: {e}")
        return False


def main():
    # normalize tracked_wallets to dict
    wallets: Dict[str, str] = (
        tracked_wallets
        if isinstance(tracked_wallets, dict)
        else {w: w[:6] + "…" + w[-4:] for w in tracked_wallets}
    )

    bootstrap_from_api()

    while True:
        start = time.time()
        for wallet, name in wallets.items():
            try:
                trades = fetch_user_trades(wallet, limit=50)
                if not trades:
                    continue

                trades.sort(
                    key=lambda t: (
                        int(t.get("timestamp", 0)),
                        t.get("transactionHash", "") or "",
                    )
                )

                for t in trades:
                    cur = ptr_of(t)
                    if last_seen.get(wallet) and cur <= last_seen[wallet]:
                        continue

                    placed = handle_trade_sync(t)
                    if placed:
                        notify_sync_copied(t, name)
                    last_seen[wallet] = cur

            except Exception as e:
                print(f"[main loop] {wallet} error: {e}")

        elapsed = time.time() - start
        time.sleep(max(0.1, POLL_INTERVAL - elapsed + 0.05))


if __name__ == "__main__":
    main()
