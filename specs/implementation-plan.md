# FinancialPlayground — Implementation Plan

## Overview

This document describes the phased build-out of the FinancialPlayground API. Each phase is self-contained and results in a testable increment of the system.

For architecture, data models, and API reference, see [`docs/design.md`](../docs/design.md).

---

## Phase 0 — Account Setup (Manual, One-Time) ✅ COMPLETE

These steps must be completed before any code can be run.

### Snaptrade
1. Sign up at [app.snaptrade.com](https://app.snaptrade.com)
2. Create a developer application
3. Copy `Client ID` and `Consumer Key` into `.env`

### Alpaca
1. Sign up at [alpaca.markets](https://alpaca.markets)
2. Navigate to the **Paper Trading** section of the dashboard
3. Generate an API Key and Secret
4. Copy `API Key` and `API Secret` into `.env`

> Do NOT use live trading keys. This app is paper-only.

---

## Phase 1 — Project Bootstrap ✅ COMPLETE

**Goal:** Runnable FastAPI app with database setup and health endpoint.

### Files to Create

**`requirements.txt`**
```
fastapi
uvicorn[standard]
snaptrade-python-sdk
alpaca-py
sqlalchemy
pydantic-settings
python-dotenv
```

**`.env.example`**
```
SNAPTRADE_CLIENT_ID=your_client_id_here
SNAPTRADE_CONSUMER_KEY=your_consumer_key_here
ALPACA_API_KEY=your_alpaca_paper_key_here
ALPACA_API_SECRET=your_alpaca_paper_secret_here
DATABASE_URL=sqlite:///./financial_playground.db
LOG_LEVEL=INFO
```

**`app/config.py`**
- Pydantic `Settings` class that reads from `.env`
- Exposes a singleton `settings` instance imported by services

**`app/database.py`**
- SQLAlchemy `create_engine` with `DATABASE_URL`
- `SessionLocal` factory
- `get_db()` FastAPI dependency (yields session, closes on exit)

**`app/models.py`**
- `SnaptradeUser` ORM model (`snaptrade_users` table)
- `TradeLog` ORM model (`trade_log` table)
- See data model in `docs/design.md` for column definitions

**`app/main.py`**
- FastAPI app with `lifespan` context manager that calls `Base.metadata.create_all()` on startup
- Register routers: `snaptrade`, `alpaca`, `portfolio`
- `GET /health` → `{ "status": "ok" }`

### Verification
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in real values
uvicorn app.main:app --reload
# → GET http://localhost:8000/health should return {"status": "ok"}
# → GET http://localhost:8000/docs should show OpenAPI UI
```

---

## Phase 2 — Snaptrade Integration ✅ COMPLETE

**Goal:** Register users, generate Robinhood OAuth URLs, retrieve holdings.

### Files to Create

**`app/services/snaptrade_service.py`**

Functions:
- `register_user(user_id: str, db: Session) -> str`
  - Calls Snaptrade `registerUser`
  - Persists `SnaptradeUser` row in DB
  - Returns `userSecret`
- `get_login_url(user_id: str, db: Session) -> str`
  - Loads `userSecret` from DB
  - Calls Snaptrade `loginUser`
  - Returns OAuth redirect URI
- `get_accounts(user_id: str, db: Session) -> list[dict]`
  - Calls Snaptrade `getUserAccountList`
  - Returns list of `{account_id, account_name, brokerage}`
- `get_holdings(user_id: str, account_id: str, db: Session) -> list[dict]`
  - Calls Snaptrade `getUserHoldings`
  - Returns normalized list of `{symbol, units, price, value}`

**`app/schemas/snaptrade.py`**
- `RegisterUserRequest`, `ConnectBrokerageRequest`
- `AccountSchema`, `HoldingSchema`

**`app/routers/snaptrade.py`**
- `POST /snaptrade/register`
- `POST /snaptrade/connect`
- `GET /snaptrade/accounts`
- `GET /snaptrade/holdings/{account_id}`

### Verification
```bash
# 1. Register user
curl -X POST http://localhost:8000/snaptrade/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "vipin"}'

# 2. Get OAuth URL
curl -X POST http://localhost:8000/snaptrade/connect \
  -H "Content-Type: application/json" \
  -d '{"user_id": "vipin", "broker": "ROBINHOOD"}'
# → Open the returned URL in a browser, log in with Robinhood

# 3. List accounts
curl "http://localhost:8000/snaptrade/accounts?user_id=vipin"

# 4. Get holdings (use account_id from step 3)
curl "http://localhost:8000/snaptrade/holdings/<account_id>?user_id=vipin"
```

---

## Phase 3 — Alpaca Paper Trading Integration ✅ COMPLETE

**Goal:** View paper account, place paper trades, manage positions.

### Files to Create

**`app/services/alpaca_service.py`**

Functions:
- `get_account() -> dict` — equity, cash, buying power
- `get_positions() -> list[dict]` — open paper positions
- `place_order(symbol, qty, side, order_type, limit_price, time_in_force, db) -> dict`
  - Submits order via Alpaca SDK
  - Logs to `trade_log` table
  - Returns order details
- `get_orders(status: str) -> list[dict]` — list orders, filterable
- `close_position(symbol: str) -> dict` — liquidate a symbol

**`app/schemas/alpaca.py`**
- `PlaceOrderRequest`, `PositionSchema`, `OrderSchema`

**`app/routers/alpaca.py`**
- `GET /alpaca/account`
- `GET /alpaca/positions`
- `POST /alpaca/orders`
- `GET /alpaca/orders`
- `DELETE /alpaca/positions/{symbol}`

### Verification
```bash
# Check account
curl http://localhost:8000/alpaca/account

# Place a test market order
curl -X POST http://localhost:8000/alpaca/orders \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "qty": 1, "side": "buy", "order_type": "market"}'

# Verify in Alpaca dashboard: paper-api.alpaca.markets

# List orders
curl http://localhost:8000/alpaca/orders

# Check positions
curl http://localhost:8000/alpaca/positions
```

---

## Phase 4 — Mirror & Compare Workflow ✅ COMPLETE

**Goal:** Mirror Robinhood holdings into Alpaca paper and compare both portfolios.

### Files to Create

**`app/schemas/portfolio.py`**
- `MirrorRequest`, `MirrorResult`, `DriftItem`, `PortfolioCompareResponse`

**`app/routers/portfolio.py`**

`POST /portfolio/mirror`
- Logic:
  1. `snaptrade_service.get_holdings(user_id, account_id)` → Robinhood positions
  2. `alpaca_service.get_positions()` → current paper positions
  3. Build set of symbols already held in paper
  4. For each Robinhood holding not in paper: call `alpaca_service.place_order(symbol, qty, "buy", "market")`
  5. Track `mirrored`, `already_held`, `skipped` (symbols Alpaca can't trade)
  6. Return `MirrorResult`

`GET /portfolio/compare`
- Logic:
  1. Fetch both sides in parallel (asyncio)
  2. Build `drift` list: for each symbol, compute `qty_diff` and `value_diff`
  3. Return `PortfolioCompareResponse`

### Verification
```bash
# Mirror Robinhood → Alpaca paper
curl -X POST http://localhost:8000/portfolio/mirror \
  -H "Content-Type: application/json" \
  -d '{"user_id": "vipin", "account_id": "<your_account_id>"}'
# → Should show mirrored symbols

# Compare both portfolios
curl "http://localhost:8000/portfolio/compare?user_id=vipin&account_id=<account_id>"
# → Should show side-by-side with drift near zero after mirror
```

---

## Phase 5 — Polish

**Goal:** Production-quality error handling, logging, and validation.

### Tasks

- [ ] Add consistent `HTTPException` handling in all routers with meaningful messages (e.g., "User not found — did you call /snaptrade/register first?")
- [ ] Add Python `logging` calls in services at DEBUG/INFO/ERROR levels
- [ ] Configure log format in `main.py` lifespan
- [ ] Validate that `qty > 0` and `limit_price > 0` (when required) in Pydantic schemas
- [ ] Handle Alpaca API errors (insufficient buying power, market closed, invalid symbol) gracefully
- [ ] Handle Snaptrade errors (user not found, account not connected) gracefully
- [x] Add `.gitignore` (exclude `.env`, `*.db`, `__pycache__`, `.venv`)

---

## Implementation Order Summary

| Phase | What Gets Built | Testable Output | Status |
|-------|----------------|-----------------|--------|
| 0 | Accounts created | API keys in hand | ✅ Complete |
| 1 | FastAPI skeleton + DB | `/health` returns 200 | ✅ Complete |
| 2 | Snaptrade integration | Robinhood holdings visible via API | ✅ Complete |
| 3 | Alpaca integration | Paper trades placed and visible in Alpaca dashboard | ✅ Complete |
| 4 | Mirror + compare | Full workflow end-to-end | ✅ Complete |
| 5 | Polish | Clean errors, logs, validation | 🔲 Not started |
