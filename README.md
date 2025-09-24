# Polytrader

![polymarket](https://github.com/user-attachments/assets/6d1edc58-7e89-4fe0-bb96-e1e843d9d0a1)





## Installation

### 1. Clone the repo

```bash
git clone https://github.com/yourname/polytrade.git
cd polytrade```

### 2. Install Dependencies
`pip install -r requirements.txt`

### 3. Setup environment variables
```
PRIVATE_KEY=0xabc123...

TG_API_ID=1234567
TG_API_HASH=abcdef1234567890abcdef
TG_CHANNEL=-1001234567890        
TG_BOT_TOKEN=123456:ABCDEF-BOTTOKEN
```

### Copytrading Mode (Live Trading)
`python main.py`

- Tracks predefined wallets
- Places mirrored trades using best market price
- Sends Telegram alert on execution

### Monitor-Only Mode (Alerts Only)
`python test.py`

- Sends Telegram notification for every new trade by tracked users
- Does not place any orders

```
tracked_wallets = {
    "0x1234...": "tommy",
    "0x5678...": "shelby",
    # Add more...
}```

# How It Works

1. Trade Polling

- Calls Polymarket’s public REST API every few seconds

- Sorts trades by (timestamp, txhash)

- Skips previously seen trades using in-memory `last_seen` cache

2. Order Execution

- Uses /price endpoint for best current price

- Places a FOK (fill-or-kill) order via py-clob-client

3. Notifications

- Telegram bot sends alerts using Markdown formatting

- Bot must be added to your channel and granted Post Messages permission

## Directory Structure
```polytrade/
│
├── main.py # Main copytrading loop (polls, filters, copies, notifies)
├── test.py # Read-only trade listener (just Telegram alerts, no copying)
│
├── utils/
│ ├── polymarket.py # Order posting, trade fetching, price querying (sync + SDK)
│ └── telegram.py # Async Telegram bot interface (send_markdown)
│
├── .env # API keys and secrets
└── requirements.txt # Python dependencies```

