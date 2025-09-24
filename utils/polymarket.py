import os
import aiohttp
from dotenv import load_dotenv
from typing import Optional, List, Dict
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

load_dotenv()

HOST = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
CHAIN_ID = 137

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER = os.getenv("POLYMARKET_PROXY_ADDRESS")

tracked_wallets: Dict[str, str] = {
    "0x751a2b86cab503496efd325c8344e10159349ea1": "Sharky6999",
    "0x6bab41a0dc40d6dd4c1a915b8c01969479fd1292": "Dropper",
    "0x44c1dfe43260c94ed4f1d00de2e1f80fb113ebc1": "tomatosauce",
    "0xd218e474776403a330142299f7796e8ba32eb5c9": "cigarettes",
    "0x6ffb4354cbe6e0f9989e3b55564ec5fb8646a834": "AgricultureSecretary",
    "0xd189664c5308903476f9f079820431e4fd7d06f4": "rwo",
    "0xa9b44dca52ed35e59ac2a6f49d1203b8155464ed": "VvVv",
}

scalar = 0.01

if not PRIVATE_KEY:
    raise RuntimeError("PRIVATE_KEY is not set")

client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=CHAIN_ID,
    signature_type=2,
    funder=FUNDER,
)
client.set_api_creds(client.create_or_derive_api_creds())


async def get_market_price(
    session: aiohttp.ClientSession, token_id: str, side: str
) -> Optional[float]:
    try:
        async with session.get(
            f"{HOST}/price", params={"token_id": token_id, "side": side}
        ) as resp:
            if resp.status != 200:
                print(f"[get_market_price] Status: {resp.status}")
                return None
            data = await resp.json()
            return float(data["price"])
    except Exception as e:
        print(f"[get_market_price] Error: {e}")
        return None


async def fetch_user_trades(
    session: aiohttp.ClientSession, wallet: str, limit: int = 50
) -> Optional[List[Dict]]:
    try:
        async with session.get(
            f"{DATA_API}/trades", params={"user": wallet, "limit": limit}
        ) as resp:
            if resp.status != 200:
                print(f"[fetch_user_trades] Status: {resp.status}")
                return None
            data = await resp.json()
            if isinstance(data, list):
                return data
            return data.get("trades", [])
    except Exception as e:
        print(f"[fetch_user_trades] Error: {e}")
        return None


async def get_total_position_value(
    session: aiohttp.ClientSession, wallet: str
) -> Optional[float]:
    try:
        async with session.get(f"{DATA_API}/value", params={"user": wallet}) as resp:
            if resp.status != 200:
                print(f"[get_total_position_value] Status: {resp.status}")
                return None
            data = await resp.json()
            return float(data["value"])
    except Exception as e:
        print(f"[get_total_position_value] Error: {e}")
        return None


def create_order(
    price: float,
    size: float,
    side: str,
    token_id: str,
    order_type: OrderType = OrderType.GTC,
) -> Optional[Dict]:
    try:
        order_args = OrderArgs(
            price=price, size=size, side=side.upper(), token_id=token_id
        )
        signed = client.create_order(order_args)
        return client.post_order(signed, order_type)
    except Exception as e:
        print(f"[create_order] Error: {e}")
        return None
