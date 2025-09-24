import asyncio
import aiohttp
import time
from typing import Dict, Tuple

from utils.polymarket import fetch_user_trades, tracked_wallets
from utils.telegram import send_markdown

# wallet -> (last_ts, last_tx)
last_seen: Dict[str, Tuple[int, str]] = {}
POLL_INTERVAL = 2.0


def ptr_of(t: dict) -> Tuple[int, str]:
    return (int(t.get("timestamp", 0)), t.get("transactionHash", "") or "")


def is_newer(prev: Tuple[int, str] | None, cur: Tuple[int, str]) -> bool:
    return prev is None or cur > prev  # tuple compare


async def notify_trade(t: dict, who: str):
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
    await send_markdown(msg)


async def initialize_from_api(session: aiohttp.ClientSession):
    for w in tracked_wallets:
        trades = await fetch_user_trades(session, w, limit=1)
        if trades:
            t = trades[0]
            last_seen[w] = ptr_of(t)
        else:
            last_seen[w] = (int(time.time()), "")


async def main():
    async with aiohttp.ClientSession() as session:
        await initialize_from_api(session)

        while True:
            for wallet, name in tracked_wallets.items():
                try:
                    trades = await fetch_user_trades(session, wallet, limit=50)
                    if not trades:
                        continue

                    # strict chronological order
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
                        await notify_trade(t, name)
                        last_seen[wallet] = cur
                except Exception as e:
                    print(f"[main loop] {wallet} error: {e}")
                time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
