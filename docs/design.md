# FinancialPlayground — Design Document

## Overview

FinancialPlayground is a Python backend API that bridges a real Robinhood brokerage account with an Alpaca paper trading account. It lets you:

- **Pull** your real Robinhood portfolio (positions, balances, history) via the Snaptrade API
- **Mirror** those positions into an Alpaca paper trading account
- **Test** new trades and strategies on Alpaca paper before committing real money on Robinhood
- **Compare** real vs. paper performance side-by-side

The system never executes real trades automatically. All Alpaca interactions are paper-only.

---

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        API Client                           │
│                  (curl / Postman / script)                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI App                            │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │ /snaptrade  │  │   /alpaca    │  │   /portfolio     │  │
│   │  router     │  │   router     │  │   router         │  │
│   └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘  │
│          │                │                   │             │
│   ┌──────▼──────┐  ┌──────▼───────┐           │             │
│   │  Snaptrade  │  │    Alpaca    │◄──────────┘             │
│   │  Service    │  │   Service    │                         │
│   └──────┬──────┘  └──────┬───────┘                        │
│          │                │                                 │
│   ┌──────▼──────┐  ┌──────▼───────┐                        │
│   │  SQLite DB  │  │  SQLite DB   │                        │
│   │ (user creds)│  │ (trade log)  │                        │
│   └─────────────┘  └──────────────┘                        │
└──────────────┬──────────────────┬───────────────────────────┘
               │                  │
               ▼                  ▼
  ┌────────────────────┐  ┌───────────────────────┐
  │   Snaptrade API    │  │  Alpaca Paper API     │
  │ api.snaptrade.com  │  │ paper-api.alpaca.     │
  │                    │  │ markets               │
  └─────────┬──────────┘  └───────────────────────┘
            │
            ▼
  ┌────────────────────┐
  │  Robinhood (real)  │
  │  via OAuth         │
  └────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Runtime | Python 3.11+ | Language |
| Web Framework | FastAPI | REST API, async support, auto docs |
| ASGI Server | uvicorn | Production-grade server |
| Brokerage Aggregator SDK | snaptrade-python-sdk | Robinhood OAuth + data pull |
| Paper Trading SDK | alpaca-py | Alpaca paper trade execution |
| ORM | SQLAlchemy 2.x | Database models + queries |
| Database | SQLite | Local persistence (tokens, trade log) |
| Validation | Pydantic v2 | Request/response schemas, settings |
| Config | python-dotenv | Load `.env` into environment |

### Why FastAPI?
- Native async support (important for concurrent API calls to Snaptrade + Alpaca)
- Auto-generated OpenAPI docs at `/docs`
- Pydantic-native, so validation and serialization are built in

### Why SQLite?
- Zero-config for a local playground app
- Can be swapped for PostgreSQL later with a connection string change

---

## Project Structure

```
FinancialPlayground/
├── app/
│   ├── main.py                  # FastAPI app entry point, lifespan
│   ├── config.py                # Pydantic Settings (loads .env)
│   ├── database.py              # SQLAlchemy engine, session factory
│   ├── models.py                # ORM table definitions
│   ├── schemas/
│   │   ├── snaptrade.py         # Pydantic request/response models for Snaptrade
│   │   ├── alpaca.py            # Pydantic request/response models for Alpaca
│   │   └── portfolio.py         # Pydantic models for compare/mirror responses
│   ├── routers/
│   │   ├── snaptrade.py         # /snaptrade/* route handlers
│   │   ├── alpaca.py            # /alpaca/* route handlers
│   │   └── portfolio.py         # /portfolio/* route handlers
│   └── services/
│       ├── snaptrade_service.py # Snaptrade SDK wrapper + business logic
│       └── alpaca_service.py    # Alpaca SDK wrapper + business logic
├── docs/
│   └── design.md               # This document
├── specs/
│   └── implementation-plan.md  # Phased implementation plan
├── .env                        # Local secrets (gitignored)
├── .env.example                # Template for required env vars
├── .gitignore
├── requirements.txt
└── ReadMe.md
```

---

## Data Model

### SQLite Tables

#### `snaptrade_users`
Stores the Snaptrade credentials generated per user after OAuth registration.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | TEXT | Primary key. App-level user identifier (e.g. "vipin") |
| `snaptrade_user_id` | TEXT | User ID registered with Snaptrade |
| `snaptrade_user_secret` | TEXT | Secret returned by Snaptrade on registration. Required for all subsequent API calls |
| `created_at` | DATETIME | Auto-set on insert |

#### `trade_log`
Audit log of every order placed on Alpaca paper through this app.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | Auto-increment primary key |
| `symbol` | TEXT | Ticker symbol (e.g. "AAPL") |
| `side` | TEXT | `buy` or `sell` |
| `qty` | REAL | Number of shares |
| `order_type` | TEXT | `market`, `limit`, `stop`, `stop_limit` |
| `limit_price` | REAL | Nullable. Used when order_type is `limit` or `stop_limit` |
| `source` | TEXT | `mirror` (auto-mirrored from Robinhood) or `manual` (user-placed) |
| `alpaca_order_id` | TEXT | Order ID returned by Alpaca |
| `status` | TEXT | Last known status from Alpaca (`pending`, `filled`, `canceled`, etc.) |
| `created_at` | DATETIME | Auto-set on insert |

### Pydantic Schemas

#### Snaptrade

```python
# Request
class RegisterUserRequest(BaseModel):
    user_id: str

class ConnectBrokerageRequest(BaseModel):
    user_id: str
    broker: str = "ROBINHOOD"

# Response
class AccountSchema(BaseModel):
    account_id: str
    account_name: str
    brokerage: str

class HoldingSchema(BaseModel):
    symbol: str
    description: str
    units: float
    price: float
    value: float
```

#### Alpaca

```python
# Request
class PlaceOrderRequest(BaseModel):
    symbol: str
    qty: float
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop", "stop_limit"] = "market"
    limit_price: Optional[float] = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"

# Response
class PositionSchema(BaseModel):
    symbol: str
    qty: float
    market_value: float
    avg_entry_price: float
    unrealized_pl: float
    unrealized_plpc: float

class OrderSchema(BaseModel):
    id: str
    symbol: str
    side: str
    qty: float
    order_type: str
    status: str
    filled_at: Optional[datetime]
    filled_avg_price: Optional[float]
```

#### Portfolio

```python
class MirrorRequest(BaseModel):
    user_id: str
    account_id: str

class MirrorResult(BaseModel):
    mirrored: list[str]      # symbols successfully ordered on Alpaca
    already_held: list[str]  # symbols already present in Alpaca paper
    skipped: list[str]       # symbols skipped (e.g. non-tradeable on Alpaca)

class PortfolioCompareResponse(BaseModel):
    robinhood: list[HoldingSchema]
    alpaca_paper: list[PositionSchema]
    drift: list[DriftItem]   # {symbol, qty_diff, value_diff}
```

---

## API Reference

### System

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/health` | Health check | None |
| GET | `/docs` | Auto-generated OpenAPI UI | None |

### Snaptrade (`/snaptrade`)

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| POST | `/snaptrade/register` | `{ user_id }` | Register a new user with Snaptrade. Returns the generated `snaptrade_user_secret`. Stores in DB. Call once per user. |
| POST | `/snaptrade/connect` | `{ user_id, broker }` | Generate OAuth redirect URL to link a brokerage (default: Robinhood). User opens URL in browser to authenticate. |
| GET | `/snaptrade/accounts` | `?user_id=` | List all connected brokerage accounts for the user. |
| GET | `/snaptrade/holdings/{account_id}` | `?user_id=` | Return current positions for the given account. |

### Alpaca (`/alpaca`)

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| GET | `/alpaca/account` | — | Return paper account info (equity, cash, buying power). |
| GET | `/alpaca/positions` | — | List current open positions in the paper account. |
| POST | `/alpaca/orders` | `PlaceOrderRequest` | Place a paper trade. Logged to `trade_log`. |
| GET | `/alpaca/orders` | `?status=open\|closed\|all` | List paper orders with optional status filter. |
| DELETE | `/alpaca/positions/{symbol}` | — | Close (liquidate) the paper position for a symbol. |

### Portfolio (`/portfolio`)

| Method | Path | Body / Params | Description |
|--------|------|---------------|-------------|
| POST | `/portfolio/mirror` | `MirrorRequest` | Pull Robinhood holdings, place matching market buys on Alpaca paper for any position not already held. Returns diff report. |
| GET | `/portfolio/compare` | `?user_id=&account_id=` | Side-by-side comparison of Robinhood holdings vs Alpaca paper positions, including drift. |

---

## External Integrations

### Snaptrade

**What it is:** A financial data aggregation API that handles OAuth connections to 100+ brokerages including Robinhood. It handles the complexity of brokerage authentication so this app doesn't need to deal with Robinhood's private APIs.

**Authentication flow:**
1. App registers a user with Snaptrade (`POST /snapTrade/registerUser`) → receives `userSecret`
2. App requests a login URL (`POST /snapTrade/login`) → receives a redirect URI
3. User opens URL in browser, logs into Robinhood, authorizes Snaptrade
4. Snaptrade stores the brokerage tokens; app can now query holdings

**SDK:** `snaptrade-python-sdk`
```python
from snaptrade_client import SnapTrade

snaptrade = SnapTrade(
    client_id=settings.SNAPTRADE_CLIENT_ID,
    consumer_key=settings.SNAPTRADE_CONSUMER_KEY
)
```

**Key SDK calls:**
```python
# Register user
response = snaptrade.authentication.register_snap_trade_user(body={"userId": user_id})
user_secret = response.body["userSecret"]

# Get OAuth URL
response = snaptrade.authentication.login_snap_trade_user(
    body={"userId": user_id, "userSecret": user_secret}
)
redirect_uri = response.body["redirectURI"]

# Get holdings
response = snaptrade.account_information.get_user_holdings(
    account_id=account_id,
    user_id=user_id,
    user_secret=user_secret
)
```

**Data returned per holding:**
- `symbol.symbol` — ticker
- `units` — number of shares
- `price` — current price
- `open_pnl` — unrealized P&L

---

### Alpaca Paper Trading

**What it is:** A commission-free brokerage with a full-featured paper trading environment. Paper accounts start with $100,000 virtual cash and behave identically to live accounts (order types, fills, market hours).

**Base URL:** `https://paper-api.alpaca.markets`

**Authentication:** API Key + Secret passed as headers (`APCA-API-KEY-ID`, `APCA-API-SECRET-KEY`)

**SDK:** `alpaca-py`
```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

client = TradingClient(
    api_key=settings.ALPACA_API_KEY,
    secret_key=settings.ALPACA_API_SECRET,
    paper=True
)
```

**Key SDK calls:**
```python
# Get account
account = client.get_account()

# Get positions
positions = client.get_all_positions()

# Place market order
order_data = MarketOrderRequest(
    symbol="AAPL",
    qty=10,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY
)
order = client.submit_order(order_data)

# Close position
client.close_position("AAPL")
```

**Order types supported:** `market`, `limit`, `stop`, `stop_limit`, `trailing_stop`

**Market hours:** Paper trading respects real market hours (9:30am–4:00pm ET). Orders placed outside hours are queued.

---

## Key Workflows

### Workflow 1 — Connect Robinhood

```
Client                    FastAPI              Snaptrade API       Robinhood
  │                          │                      │                  │
  │  POST /snaptrade/register│                      │                  │
  │  { user_id: "vipin" }    │                      │                  │
  │─────────────────────────►│                      │                  │
  │                          │  registerUser(vipin) │                  │
  │                          │─────────────────────►│                  │
  │                          │  ◄── userSecret ─────│                  │
  │                          │  [store in SQLite]   │                  │
  │  ◄── { userSecret } ─────│                      │                  │
  │                          │                      │                  │
  │  POST /snaptrade/connect  │                      │                  │
  │  { user_id: "vipin" }    │                      │                  │
  │─────────────────────────►│                      │                  │
  │                          │  loginUser(vipin)    │                  │
  │                          │─────────────────────►│                  │
  │                          │  ◄── redirectURI ────│                  │
  │  ◄── { oauth_url } ──────│                      │                  │
  │                          │                      │                  │
  │  [User opens oauth_url in browser]              │                  │
  │                          │                      │  OAuth login     │
  │                          │                      │─────────────────►│
  │                          │                      │  ◄── authorized ─│
```

### Workflow 2 — Mirror Robinhood → Alpaca Paper

```
Client              FastAPI          SnaptradeService    AlpacaService
  │                    │                    │                 │
  │  POST /portfolio/  │                    │                 │
  │  mirror            │                    │                 │
  │  { user_id,        │                    │                 │
  │    account_id }    │                    │                 │
  │───────────────────►│                    │                 │
  │                    │  get_holdings()    │                 │
  │                    │───────────────────►│                 │
  │                    │  ◄── [positions] ──│                 │
  │                    │                    │                 │
  │                    │  get_positions()   │                 │
  │                    │───────────────────────────────────► │
  │                    │  ◄── [paper positions] ─────────────│
  │                    │                    │                 │
  │                    │  [diff: what's missing in paper]    │
  │                    │                    │                 │
  │                    │  for each missing symbol:           │
  │                    │    place_order(symbol, qty, BUY)    │
  │                    │───────────────────────────────────► │
  │                    │  ◄── [order confirmations] ─────────│
  │                    │                    │                 │
  │                    │  [log to trade_log]│                 │
  │                    │                    │                 │
  │  ◄── MirrorResult ─│                    │                 │
```

### Workflow 3 — Place a Test Trade

```
Client                 FastAPI              AlpacaService
  │                       │                      │
  │  POST /alpaca/orders  │                      │
  │  { symbol: "NVDA",    │                      │
  │    qty: 5,            │                      │
  │    side: "buy",       │                      │
  │    order_type:        │                      │
  │    "limit",           │                      │
  │    limit_price: 900 } │                      │
  │──────────────────────►│                      │
  │                       │  submit_order(...)   │
  │                       │─────────────────────►│
  │                       │  ◄── order object ───│
  │                       │  [log to trade_log]  │
  │  ◄── OrderSchema ─────│                      │
```

### Workflow 4 — Compare Portfolios

```
Client                 FastAPI          SnaptradeService    AlpacaService
  │                       │                    │                 │
  │  GET /portfolio/      │                    │                 │
  │  compare?user_id=     │                    │                 │
  │  vipin&account_id=... │                    │                 │
  │──────────────────────►│                    │                 │
  │                       │  get_holdings()    │                 │
  │                       │───────────────────►│                 │
  │                       │  ◄── RH positions ─│                 │
  │                       │                    │                 │
  │                       │  get_positions()   │                 │
  │                       │───────────────────────────────────► │
  │                       │  ◄── paper positions ───────────────│
  │                       │                    │                 │
  │                       │  [compute drift]   │                 │
  │  ◄── CompareResponse ─│                    │                 │
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SNAPTRADE_CLIENT_ID` | Yes | Snaptrade developer app Client ID |
| `SNAPTRADE_CONSUMER_KEY` | Yes | Snaptrade developer app Consumer Key (used for HMAC signing) |
| `ALPACA_API_KEY` | Yes | Alpaca paper trading API key |
| `ALPACA_API_SECRET` | Yes | Alpaca paper trading API secret |
| `DATABASE_URL` | No | SQLAlchemy DB URL. Defaults to `sqlite:///./financial_playground.db` |
| `LOG_LEVEL` | No | Logging level. Defaults to `INFO` |

---

## Security Notes

- **`snaptrade_user_secret`** must be stored securely. It grants full access to the user's connected brokerage data. In this playground it's stored in SQLite — for any production deployment, encrypt it at rest or use a secrets manager.
- **Alpaca keys** should be scoped to paper trading only. Never use live trading keys with this app.
- **No real trades** are executed by this app. All Alpaca calls go to `paper-api.alpaca.markets`.
- **`.env` must be gitignored** — never commit API keys. The repo includes `.env.example` as a safe template.
- Snaptrade OAuth tokens for Robinhood are held by Snaptrade, not by this app. This app only stores the Snaptrade `userSecret`, not any Robinhood credentials.
