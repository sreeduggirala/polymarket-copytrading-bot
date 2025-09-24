import asyncio
import time
from typing import Dict, List, Tuple
from utils.polymarket import fetch_user_trades
from utils.telegram import send_markdown

user_polymarket_address = "8YpWjJFkHaz54gqgCSbWgenmHE2STqBQveFjMin6PACF"  # Solana


LastPtr = Tuple[int, str]
last_seen: Dict[str, LastPtr] = {}

tracked_wallets = []
address_to_scale = {}


def ptr_of(t: dict) -> LastPtr:
    ts = int(t.get("timestamp", 0))
    tx = t.get("transactionHash", "") or ""
    return (ts, tx)


def is_newer(prev: LastPtr | None, cur: LastPtr) -> bool:
    if prev is None:
        return True
    # compare by (timestamp, txhash)
    return cur > prev


async def notify_trade(t: dict, addr_to_name: Dict[str, str]):
    addr = t["proxyWallet"].lower()
    who = addr_to_name.get(addr, addr[:6] + "…" + addr[-4:])
    side = t["side"]
    size = t["size"]
    price = t["price"]
    outcome = t.get("outcome") or ""
    title = t.get("title") or t.get("slug") or ""
    token_id = t.get("asset")  # use this when placing orders
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(t["timestamp"])))

    msg = (
        f"*{who}* — *{side}* {size} @ {price}\n"
        f"`{outcome}` — {title}\n"
        f"`token_id:` `{token_id}`\n"
        f"`tx:` `{t.get('transactionHash','')}`\n"
        f"{ts} UTC"
    )
    await send_markdown(msg)


async def watch_users(addresses: List[str], addr_to_name: Dict[str, str], period_s=2.0):
    addrs = [a.lower() for a in addresses]
    while True:
        start = time.time()
        for addr in addrs:
            try:
                trades = fetch_user_trades(addr, limit=50)
                # process oldest→newest so we don’t miss anything
                for t in reversed(trades):
                    cur = ptr_of(t)
                    if is_newer(last_seen.get(addr), cur):
                        await notify_trade(t, addr_to_name)
                        # TODO: when you’re ready to copy:
                        # await copy_trade(t)  # use t["asset"] as token_id, t["side"], t["price"], t["size"]
                        last_seen[addr] = cur
            except Exception as e:
                # optional: alert/log
                # await send_markdown(f"_watch error {addr}_: `{e}`")
                pass
        elapsed = time.time() - start
        await asyncio.sleep(max(0.1, period_s - elapsed + 0.05))
