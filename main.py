# main.py — copytrader loop: 1) get new trades, 2) mirror, 3) announce
import os, json, time, asyncio
from typing import Dict, Tuple
from dotenv import load_dotenv

from polymarket import (
    fetch_trades_for_user, trade_ptr,
    market_buy_notional, market_sell_notional,
)
from telegram import send_markdown

load_dotenv()

# --- config ---
TRADE_SCALE = float(os.getenv("TRADE_SCALE", "1.0"))   # 1.0=same notional as source
POLL_SEC = float(os.getenv("POLL_SEC", "2.0"))

TARGETS: Dict[str,str] = {  # wallet -> name
    "0xd218e474776403a330142299f7796e8ba32eb5c9": "cigarettes",
    # add more …
}

CURSORS_FILE = os.getenv("CURSORS_FILE", "last_seen.json")

def load_cursors() -> Dict[str, Tuple[int,str,int]]:
    try:
        data = json.load(open(CURSORS_FILE))
        return {w: tuple(v) for w, v in data.items()}
    except Exception:
        return {}

def save_cursors(c):
    json.dump({w:list(v) for w,v in c.items()}, open(CURSORS_FILE, "w"))

def format_announce(t: dict, name: str, ok: bool) -> str:
    side = "BUY" if t.get("is_buy") else "SELL"
    title = t.get("title") or t.get("question") or ""
    price = float(t.get("price") or 0.0)
    amt   = float(t.get("amount") or 0.0)
    when  = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(t.get("timestamp") or 0)))
    status = "✅ mirrored" if ok else "❌ mirror failed"
    return (
        f"*{name}* — *{side}* {amt:.2f} @ {price:.3f}\n"
        f"{title}\n"
        f"`token_id:` `{t.get('token_id','')}`\n"
        f"`tx:` `{t.get('tx_hash','')}`\n"
        f"{when}\n\n"
        f"{status}"
    )

def mirror_trade(t: dict) -> bool:
    # Polymarket data API "amount" is USDC notional for the trade (buyer/seller view).
    notional = float(t.get("amount") or 0.0) * TRADE_SCALE
    token_id = t.get("token_id")
    if not token_id or notional <= 0:
        return False
    if t.get("is_buy"):
        return market_buy_notional(token_id, notional)
    else:
        return market_sell_notional(token_id, notional)

def main():
    cursors = load_cursors()
    print(f"[init] TRADE_SCALE={TRADE_SCALE}, polling={POLL_SEC}s; wallets={len(TARGETS)}")

    while True:
        sweep = time.time()
        for wallet, name in TARGETS.items():
            try:
                ls = cursors.get(wallet, (0,"",0))
                items = fetch_trades_for_user(wallet, limit=50)   # newest first
                if items:
                    newest = trade_ptr(items[0])
                    print(f"[poll] {name} count={len(items)} newest={newest} last_seen={ls}")

                # iterate newest->oldest; send only strictly newer
                for t in items:
                    cur = trade_ptr(t)
                    if cur > ls:
                        ok = mirror_trade(t)
                        msg = format_announce(t, name, ok)
                        asyncio.run(send_markdown(msg))
                        cursors[wallet] = cur
                        ls = cur
                    else:
                        # debug skip
                        # print(f"[skip] {name} {cur} <= {ls}")
                        pass
            except Exception as e:
                print(f"[error] {name}: {e}")
        save_cursors(cursors)

        # heartbeat every ~10 mins
        if int(time.time()) % 600 < 2:
            asyncio.run(send_markdown("_heartbeat: copytrader alive_"))

        # keep cadence
        time.sleep(max(0.1, POLL_SEC - (time.time() - sweep)))

if __name__ == "__main__":
    main()
