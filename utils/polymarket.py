import os
import aiohttp
from dotenv import load_dotenv
from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

load_dotenv()

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
DATA_API = "https://data-api.polymarket.com"

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYMARKET_PROXY_ADDRESS = os.getenv("POLYMARKET_PROXY_ADDRESS")

if not PRIVATE_KEY:
    raise RuntimeError("PRIVATE_KEY is not set")

client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    signature_type=2,
    funder=POLYMARKET_PROXY_ADDRESS,
)

client.set_api_creds(client.create_or_derive_api_creds())


async def get_market_price(
    session: aiohttp.ClientSession, token_id: str, side: str
) -> Optional[float]:
    url = f"{HOST}/price"
    try:
        async with session.get(
            url, params={"token_id": token_id, "side": side}
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return float(data["price"])
    except Exception as e:
        print(f"[get_market_price] Error: {e}")
        return None


def create_order(
    price: float,
    size: float,
    side: str,
    token_id: str,
    order_type: OrderType = OrderType.GTC,
) -> Optional[dict]:
    try:
        order_args = OrderArgs(price=price, size=size, side=side, token_id=token_id)
        signed = client.create_order(order_args)
        return client.post_order(signed, order_type)
    except Exception as e:
        print(f"[create_order] Error: {e}")
        return None


async def fetch_user_trades(
    session: aiohttp.ClientSession, wallet: str, limit: int = 50
) -> Optional[list[dict]]:
    url = f"{DATA_API}/trades"
    try:
        async with session.get(url, params={"user": wallet, "limit": limit}) as resp:
            resp.raise_for_status()
            return await resp.json()
    except Exception as e:
        print(f"[fetch_user_trades] Error: {e}")
        return None


async def get_total_position_value(
    session: aiohttp.ClientSession, wallet: str
) -> Optional[float]:
    url = f"{DATA_API}/value"
    try:
        async with session.get(url, params={"user": wallet}) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return float(data["value"])
    except Exception as e:
        print(f"[get_total_position_value] Error: {e}")
        return None
