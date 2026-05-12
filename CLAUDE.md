# FinancialPlayground — Claude Instructions

## Running the app

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Running tests

```bash
.venv/bin/pytest tests/ -v
```

No real API keys are needed to run tests — all external SDK calls are mocked. A dummy `.env` with placeholder values is sufficient.

---

## Architecture decisions

- **Paper trading only.** All Alpaca interactions use `paper=True`. Never switch to live keys.
- **Snaptrade for Robinhood.** Robinhood data is accessed via Snaptrade OAuth — the app never holds Robinhood credentials directly, only the Snaptrade `userSecret`.
- **SQLite for local dev.** Zero config. Can be swapped to Postgres by changing `DATABASE_URL`.

---

## Key implementation decisions (from code review, April 2026)

### `Base` lives in `models.py`, not `database.py`
`main.py` imports `Base` from `app.models`, not `app.database`. `database.py` only owns the engine and session factory.

### Use `lifespan` context manager, not `@app.on_event`
`@app.on_event("startup")` is deprecated in FastAPI. Always use the `asynccontextmanager` lifespan pattern in `main.py`.

### Use `sqlalchemy.orm.declarative_base`, not `sqlalchemy.ext.declarative`
The `ext.declarative` path is the SQLAlchemy 1.x import and deprecated in 2.x.

### Alpaca order type is `order.type`, not `order.order_class`
`order_class` is the bracket-class field ("simple", "bracket", "oco"). The market/limit type is on `order.type`.

### `place_order` accepts a `source` parameter
Defaults to `"manual"`. Phase 4 mirror workflow must pass `source="mirror"` so the `trade_log` table correctly distinguishes mirror-placed vs user-placed orders.

### `time_in_force` must be forwarded, not hardcoded
`place_order` converts the string arg to `TimeInForce(time_in_force)` enum and passes it through to the Alpaca SDK request. Do not hardcode `TimeInForce.DAY`.

---

## Test conventions

### Use `conftest.py` for shared DB setup — never duplicate it in test files
All test DB configuration lives in `tests/conftest.py`. Individual test files import `TEST_ENGINE` from there. This prevents engine conflicts when pytest loads multiple test modules.

### Use `StaticPool` for in-memory SQLite tests
```python
from sqlalchemy.pool import StaticPool
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
```
Without `StaticPool`, each SQLAlchemy session opens a separate SQLite connection, each getting its own isolated in-memory database. Fixtures that create tables on one connection become invisible to the route handler's session.

### Override `get_db` once in `conftest.py`
```python
app.dependency_overrides[get_db] = override_get_db
```
If multiple test files each set `app.dependency_overrides[get_db]`, the last file loaded wins for the entire test run. Set it once in `conftest.py`.

### `reset_db` fixture is `autouse=True`
Tables are created before each test and dropped after. This gives each test a clean slate without requiring an in-memory DB per test.

### Each test is idempotent
Do not rely on state from a previous test. Any DB rows a test needs must be inserted by that test (or its fixture).
