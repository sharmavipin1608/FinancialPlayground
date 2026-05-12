from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.main import app
from app.models import TradeLog
from tests.conftest import TEST_ENGINE

client = TestClient(app)


class MockAccount:
    def __init__(self, equity, cash, buying_power):
        self.equity = equity
        self.cash = cash
        self.buying_power = buying_power


class MockPosition:
    def __init__(self, symbol, qty, market_value, avg_entry_price, unrealized_pl, unrealized_plpc):
        self.symbol = symbol
        self.qty = qty
        self.market_value = market_value
        self.avg_entry_price = avg_entry_price
        self.unrealized_pl = unrealized_pl
        self.unrealized_plpc = unrealized_plpc


class MockOrder:
    def __init__(self, id_, symbol, qty, side, type_, status, filled_at=None, filled_avg_price=None):
        self.id = id_
        self.symbol = symbol
        self.qty = qty
        self.side = side
        self.type = type_
        self.status = status
        self.filled_at = filled_at
        self.filled_avg_price = filled_avg_price


# ── /alpaca/account ────────────────────────────────────────────────────────────

@patch("app.services.alpaca_service._alpaca_client")
def test_account_info(mock_client):
    mock_client.get_account.return_value = MockAccount(
        equity="100000", cash="50000", buying_power="150000"
    )
    response = client.get("/alpaca/account")
    assert response.status_code == 200
    assert response.json() == {"equity": "100000", "cash": "50000", "buying_power": "150000"}


@patch("app.services.alpaca_service._alpaca_client")
def test_account_info_sdk_error_returns_500(mock_client):
    mock_client.get_account.side_effect = Exception("Alpaca unavailable")
    response = client.get("/alpaca/account")
    assert response.status_code == 500
    assert "Alpaca unavailable" in response.json()["detail"]


# ── /alpaca/positions ──────────────────────────────────────────────────────────

@patch("app.services.alpaca_service._alpaca_client")
def test_list_positions(mock_client):
    mock_client.get_all_positions.return_value = [
        MockPosition("AAPL", "10", "1500", "150", "100", "0.07"),
        MockPosition("TSLA", "5", "4000", "800", "200", "0.05"),
    ]
    response = client.get("/alpaca/positions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0] == {
        "symbol": "AAPL", "qty": 10.0, "market_value": 1500.0,
        "avg_entry_price": 150.0, "unrealized_pl": 100.0, "unrealized_plpc": 0.07,
    }


@patch("app.services.alpaca_service._alpaca_client")
def test_list_positions_empty(mock_client):
    mock_client.get_all_positions.return_value = []
    response = client.get("/alpaca/positions")
    assert response.status_code == 200
    assert response.json() == []


# ── /alpaca/orders (POST) ──────────────────────────────────────────────────────

@patch("app.services.alpaca_service._alpaca_client")
def test_create_market_order(mock_client):
    mock_client.submit_order.return_value = MockOrder(
        id_="order123", symbol="AAPL", qty="1", side="buy", type_="market", status="filled"
    )
    response = client.post("/alpaca/orders", json={"symbol": "AAPL", "qty": 1, "side": "buy", "order_type": "market"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "order123"
    assert data["order_type"] == "market"
    assert data["status"] == "filled"


@patch("app.services.alpaca_service._alpaca_client")
def test_create_market_order_logs_to_db(mock_client):
    mock_client.submit_order.return_value = MockOrder(
        id_="order123", symbol="AAPL", qty="1", side="buy", type_="market", status="filled"
    )
    client.post("/alpaca/orders", json={"symbol": "AAPL", "qty": 1, "side": "buy", "order_type": "market"})

    db = Session(bind=TEST_ENGINE)
    log = db.query(TradeLog).filter(TradeLog.alpaca_order_id == "order123").first()
    assert log is not None
    assert log.symbol == "AAPL"
    assert log.side == "buy"
    assert log.source == "manual"
    db.close()


@patch("app.services.alpaca_service._alpaca_client")
def test_create_limit_order(mock_client):
    mock_client.submit_order.return_value = MockOrder(
        id_="order456", symbol="NVDA", qty="5", side="buy", type_="limit", status="accepted"
    )
    response = client.post("/alpaca/orders", json={
        "symbol": "NVDA", "qty": 5, "side": "buy",
        "order_type": "limit", "limit_price": 900.0,
    })
    assert response.status_code == 200
    assert response.json()["order_type"] == "limit"

    db = Session(bind=TEST_ENGINE)
    log = db.query(TradeLog).filter(TradeLog.alpaca_order_id == "order456").first()
    assert log.limit_price == 900.0
    db.close()


@patch("app.services.alpaca_service._alpaca_client")
def test_create_limit_order_missing_price_returns_400(mock_client):
    """Limit order without limit_price should return 400."""
    response = client.post("/alpaca/orders", json={
        "symbol": "NVDA", "qty": 5, "side": "buy", "order_type": "limit"
    })
    assert response.status_code == 400
    assert "limit_price" in response.json()["detail"]


def test_create_order_invalid_side_returns_422():
    """Pydantic validation: side must be 'buy' or 'sell'."""
    response = client.post("/alpaca/orders", json={"symbol": "AAPL", "qty": 1, "side": "long", "order_type": "market"})
    assert response.status_code == 422


def test_create_order_invalid_order_type_returns_422():
    """Pydantic validation: order_type must be 'market' or 'limit'."""
    response = client.post("/alpaca/orders", json={"symbol": "AAPL", "qty": 1, "side": "buy", "order_type": "stop"})
    assert response.status_code == 422


@patch("app.services.alpaca_service._alpaca_client")
def test_create_order_gtc_time_in_force(mock_client):
    """time_in_force parameter should be forwarded, not silently ignored."""
    mock_client.submit_order.return_value = MockOrder(
        id_="order789", symbol="AAPL", qty="1", side="buy", type_="market", status="accepted"
    )
    client.post("/alpaca/orders", json={
        "symbol": "AAPL", "qty": 1, "side": "buy",
        "order_type": "market", "time_in_force": "gtc",
    })
    call_kwargs = mock_client.submit_order.call_args[0][0]
    from alpaca.trading.enums import TimeInForce
    assert call_kwargs.time_in_force == TimeInForce.GTC


# ── /alpaca/orders (GET) ───────────────────────────────────────────────────────

@patch("app.services.alpaca_service._alpaca_client")
def test_list_orders(mock_client):
    mock_client.get_orders.return_value = [
        MockOrder("order1", "AAPL", "1", "buy", "market", "filled"),
        MockOrder("order2", "TSLA", "2", "sell", "limit", "open"),
    ]
    response = client.get("/alpaca/orders", params={"status": "all"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "order1"
    assert data[0]["order_type"] == "market"
    assert data[1]["order_type"] == "limit"


@patch("app.services.alpaca_service._alpaca_client")
def test_list_orders_empty(mock_client):
    mock_client.get_orders.return_value = []
    response = client.get("/alpaca/orders")
    assert response.status_code == 200
    assert response.json() == []


# ── /alpaca/positions/{symbol} (DELETE) ───────────────────────────────────────

@patch("app.services.alpaca_service._alpaca_client")
def test_close_position(mock_client):
    mock_client.close_position.return_value = {"status": "success"}
    response = client.delete("/alpaca/positions/AAPL")
    assert response.status_code == 200
    assert response.json() == {"symbol": "AAPL", "result": {"status": "success"}}
    mock_client.close_position.assert_called_once_with("AAPL")


@patch("app.services.alpaca_service._alpaca_client")
def test_close_position_not_found_returns_400(mock_client):
    mock_client.close_position.side_effect = Exception("position not found for FAKE")
    response = client.delete("/alpaca/positions/FAKE")
    assert response.status_code == 400
    assert "position not found" in response.json()["detail"]


# ── /health ────────────────────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
