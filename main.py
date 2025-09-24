import asyncio
import aiohttp
import time
from typing import Dict, Tuple

from utils.polymarket import (
    fetch_user_trades,
    get_market_price,
    create_order,
    tracked_wallets,
)
from utils.telegram import send_markdown


# wallet -> (timestamp, transactionHash)
last_seen: Dict[str, Tuple[int, str]] = {}

POLL_INTERVAL = 2.0  # seconds


async def handle_trade(session: aiohttp.ClientSession, trade: dict, name: str) -> None:
    try:
        token_id = trade["asset"]
        side = trade["side"]  # "BUY"/"SELL"
        size = float(trade["size"])
        ref_price = float(trade["price"])
        timestamp = int(trade["timestamp"])
        tx = trade.get("transactionHash", "")

        market_price = await get_market_price(session, token_id, side)
        if market_price is None:
            return

        resp = create_order(price=market_price, size=size, side=side, token_id=token_id)
        if not resp:
            return

        msg = (
            f"*Copied Trade*\n"
            f"{name} — {side} {size} @ {ref_price}\n"
            f"`token_id:` `{token_id}`\n"
            f"`tx:` `{tx}`\n"
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))} UTC"
        )
        await send_markdown(msg)

    except Exception as e:
        print(f"[handle_trade] Error: {e}")


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                for wallet, name in tracked_wallets.items():
                    # ✅ pass session AND wallet, and await
                    trades = await fetch_user_trades(session, wallet, limit=50)
                    if not trades:
                        continue

                    # process oldest → newest so bursts aren’t skipped
                    trades.sort(key=lambda t: int(t["timestamp"]))

                    for t in trades:
                        tx = t.get("transactionHash", "") or ""
                        ts = int(t["timestamp"])
                        ptr = last_seen.get(wallet)

                        if ptr and (ts, tx) <= ptr:
                            continue

                        await handle_trade(session, t, name)
                        last_seen[wallet] = (ts, tx)

                await asyncio.sleep(POLL_INTERVAL)

            except Exception as e:
                print(f"[main loop] Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
