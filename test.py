import time
import asyncio
from typing import Dict, Tuple
import requests

from utils.polymarket import tracked_wallets  # dict[wallet]->name OR list[str]
from utils.telegram import send_markdown  # async function

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

DATA_API = "https://data-api.polymarket.com"
POLL_INTERVAL = 2.0  # seconds

# wallet -> (last_ts, last_tx)
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


def is_newer(prev: LastPtr | None, cur: LastPtr) -> bool:
    return prev is None or cur > prev


def notify_trade_sync(t: dict, who: str):
    side, size, price = t["side"], t["size"], t["price"]
    outcome = t.get("outcome") or ""
    title = t.get("title") or t.get("slug") or ""
    token_id = t.get("asset")
    tx = t.get("transactionHash", "") or ""
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(t["timestamp"])))
    msg = (
        f"*{who}* — *{side}* {size} @ {price}\n"
        f"`{outcome}` — {title}\n"
        f"`token_id:` `{token_id}`\n"
        f"`tx:` `{tx}`\n"
        f"{ts_str} UTC"
    )
    asyncio.run(send_markdown(msg))  # call async notifier from sync code


def bootstrap_from_api():
    for w in (
        tracked_wallets if isinstance(tracked_wallets, list) else tracked_wallets.keys()
    ):
        trades = fetch_user_trades(w, limit=1)  # newest
        if trades:
            last_seen[w] = ptr_of(trades[0])
        else:
            last_seen[w] = (int(time.time()), "")


def main():
    # tracked_wallets can be dict or list; normalize to dict for names
    if isinstance(tracked_wallets, dict):
        wallets = tracked_wallets
    else:
        wallets = {w: w[:6] + "…" + w[-4:] for w in tracked_wallets}

    bootstrap_from_api()

    while True:
        start = time.time()
        for wallet, name in wallets.items():
            try:
                trades = fetch_user_trades(wallet, limit=50)
                if not trades:
                    continue

                # strict chronological order (ts, tx)
                trades.sort(
                    key=lambda x: (
                        int(x.get("timestamp", 0)),
                        x.get("transactionHash", "") or "",
                    )
                )

                for t in trades:
                    cur = ptr_of(t)
                    if not is_newer(last_seen.get(wallet), cur):
                        continue
                    notify_trade_sync(t, name)
                    last_seen[wallet] = cur
            except Exception as e:
                print(f"[test loop] {wallet} error: {e}")

        elapsed = time.time() - start
        time.sleep(max(0.1, POLL_INTERVAL - elapsed + 0.05))


if __name__ == "__main__":
    main()
