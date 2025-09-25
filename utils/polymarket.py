# polymarket.py — thin Polymarket wrappers (Data API + CLOB; SELL uses shares)
import os
import requests
from typing import Dict, List, Tuple, Optional, Any

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

DATA_API = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER = os.getenv("POLYMARKET_PROXY_ADDRESS")
if not PRIVATE_KEY or not FUNDER:
    raise RuntimeError("Set PRIVATE_KEY and POLYMARKET_PROXY_ADDRESS in .env")

_client: Optional[ClobClient] = None
def clob() -> ClobClient:
    global _client
    if _client is None:
        c = ClobClient(
            host=CLOB_HOST,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            signature_type=2,
            funder=FUNDER,
        )
        creds = c.create_or_derive_api_creds()
        c.set_api_creds(creds)
        _client = c
    return _client

# ---------- Data API (for tracking other wallets) ----------
def fetch_trades_for_user(user: str, limit: int = 50) -> List[Dict[str, Any]]:
    r = requests.get(f"{DATA_API}/trades", params={"user": user, "limit": limit}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []

def trade_ptr(t: Dict[str, Any]) -> Tuple[int, str, int]:
    ts = int(t.get("timestamp") or 0)
    tx = t.get("tx_hash") or ""
    li = int(t.get("log_index") or 0)
    return (ts, tx, li)

# ---------- Quotes ----------
def best_quotes(token_id: str) -> Tuple[Optional[float], Optional[float]]:
    """Return (best_bid_price, best_ask_price) as floats using level 0, or (None, None)."""
    ob = clob().get_order_book(token_id)
    best_bid = float(ob.bids[0].price) if ob and ob.bids else None
    best_ask = float(ob.asks[0].price) if ob and ob.asks else None
    return best_bid, best_ask

# ---------- Market order helpers ----------
def market_buy_notional(token_id: str, notional_usdc: float) -> bool:
    """BUY market: amount = USDC notional (per docs)."""
    if notional_usdc <= 0:
        return False
    args = MarketOrderArgs(token_id=str(token_id), amount=float(notional_usdc), side=BUY)
    order = clob().create_market_order(args)
    resp = clob().post_order(order, OrderType.FOK)
    return bool(resp.get("success"))

def market_sell_notional(token_id: str, notional_usdc: float) -> bool:
    """
    SELL market must submit SHARES (per docs). We convert desired USDC notional
    into shares using the current best bid. If no bid, we skip.
    """
    if notional_usdc <= 0:
        return False
    best_bid, _ = best_quotes(token_id)
    if not best_bid or best_bid <= 0:
        return False
    shares = float(notional_usdc) / float(best_bid)  # convert notional -> shares
    if shares <= 0:
        return False
    args = MarketOrderArgs(token_id=str(token_id), amount=shares, side=SELL)
    order = clob().create_market_order(args)
    resp = clob().post_order(order, OrderType.FOK)
    return bool(resp.get("success"))
