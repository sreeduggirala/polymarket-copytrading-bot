# telegram.py — minimal async Telegram sender using Bot API (no Telethon)
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHANNEL = os.getenv("TG_CHANNEL")  # channel ID like -100xxxxxxxxxx or @handle

if not TG_BOT_TOKEN or not TG_CHANNEL:
    raise RuntimeError("Set TG_BOT_TOKEN and TG_CHANNEL in .env")

API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

async def send_markdown(text: str):
    """Fire-and-forget Markdown message."""
    async with aiohttp.ClientSession() as s:
        async with s.post(API, json={
            "chat_id": TG_CHANNEL,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=20) as r:
            if r.status != 200:
                body = await r.text()
                raise RuntimeError(f"Telegram error {r.status}: {body}")
