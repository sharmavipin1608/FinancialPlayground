# FinancialPlayground

A Python backend API for safely testing stock trading strategies before committing real money.

- **Pull** your real Robinhood portfolio via [Snaptrade](https://snaptrade.com) (OAuth — no credentials stored)
- **Mirror** those positions into an [Alpaca](https://alpaca.markets) paper trading account
- **Test** trades and strategies on paper, compare performance against your real portfolio

No real trades are ever executed automatically. All Alpaca interactions use the paper trading environment.

---

## Prerequisites

You need accounts with two services before running this app:

### 1. Snaptrade (Robinhood data)
- Sign up at [app.snaptrade.com](https://app.snaptrade.com)
- Create a developer application
- You will receive a **Client ID** and **Consumer Key**
- Free tier is sufficient

### 2. Alpaca (Paper trading)
- Sign up at [alpaca.markets](https://alpaca.markets)
- Navigate to the **Paper Trading** section of your dashboard
- Generate an **API Key** and **API Secret**
- Use paper trading keys only — do not use live trading keys with this app

### 3. Python
- Python 3.11 or higher

---

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd FinancialPlayground

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and fill in your API keys

# 5. Run the API
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive API docs: `http://localhost:8000/docs`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Description | Where to find it |
|----------|-------------|-----------------|
| `SNAPTRADE_CLIENT_ID` | Snaptrade developer app Client ID | [app.snaptrade.com](https://app.snaptrade.com) → your app |
| `SNAPTRADE_CONSUMER_KEY` | Snaptrade Consumer Key (used for request signing) | Same as above |
| `ALPACA_API_KEY` | Alpaca paper trading API key | Alpaca dashboard → Paper Trading → API Keys |
| `ALPACA_API_SECRET` | Alpaca paper trading API secret | Same as above |
| `DATABASE_URL` | SQLAlchemy connection string | Defaults to `sqlite:///./financial_playground.db` |
| `LOG_LEVEL` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`. Defaults to `INFO` |

---

## Core Workflow

### Step 1 — Register and connect Robinhood

```bash
# Register your user
curl -X POST http://localhost:8000/snaptrade/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "me"}'

# Get the Robinhood OAuth URL
curl -X POST http://localhost:8000/snaptrade/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "me", "broker": "ROBINHOOD"}'

# Open the returned URL in a browser and log in with Robinhood
# Then list your accounts
curl "http://localhost:8000/snaptrade/accounts?user_id=me"
```

### Step 2 — Mirror your portfolio to Alpaca paper

```bash
curl -X POST http://localhost:8000/portfolio/mirror \
  -H "Content-Type: application/json" \
  -d '{"user_id": "me", "account_id": "<account_id_from_step_1>"}'
```

### Step 3 — Test a trade on paper

```bash
curl -X POST http://localhost:8000/alpaca/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol": "NVDA", "qty": 5, "side": "buy", "order_type": "market"}'
```

### Step 4 — Compare real vs. paper

```bash
curl "http://localhost:8000/portfolio/compare?user_id=me&account_id=<account_id>"
```

---

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/snaptrade/register` | Register a user with Snaptrade |
| POST | `/snaptrade/connect` | Get Robinhood OAuth URL |
| GET | `/snaptrade/accounts` | List connected brokerage accounts |
| GET | `/snaptrade/holdings/{account_id}` | Get Robinhood positions |
| GET | `/alpaca/account` | Paper account balance and equity |
| GET | `/alpaca/positions` | Open paper positions |
| POST | `/alpaca/orders` | Place a paper trade |
| GET | `/alpaca/orders` | List paper orders |
| DELETE | `/alpaca/positions/{symbol}` | Close a paper position |
| POST | `/portfolio/mirror` | Mirror Robinhood → Alpaca paper |
| GET | `/portfolio/compare` | Side-by-side portfolio comparison |

Full API documentation is available at `/docs` when the server is running, and in [`docs/design.md`](docs/design.md).

---

## Project Structure

```
FinancialPlayground/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings (loaded from .env)
│   ├── database.py              # SQLAlchemy setup
│   ├── models.py                # DB table definitions
│   ├── schemas/                 # Pydantic request/response models
│   ├── routers/                 # Route handlers
│   └── services/                # Business logic + SDK wrappers
├── docs/
│   └── design.md                # Full architecture & design document
├── specs/
│   └── implementation-plan.md   # Phased build plan
├── .env.example                 # Environment variable template
├── requirements.txt
└── ReadMe.md
```

---

## Documentation

- **Architecture, data model, API reference, workflows:** [`docs/design.md`](docs/design.md)
- **Phased implementation plan:** [`specs/implementation-plan.md`](specs/implementation-plan.md)
