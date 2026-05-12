from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.main import app
from app.models import SnaptradeUser
from tests.conftest import TEST_ENGINE

client = TestClient(app)


class MockResponse:
    def __init__(self, body):
        self.body = body


# ── /snaptrade/register ────────────────────────────────────────────────────────

@patch("app.services.snaptrade_service._snaptrade_client")
def test_register_user_success(mock_client):
    mock_client.authentication.register_snap_trade_user.return_value = MockResponse({
        "userSecret": "secret123",
        "userId": "snap123",
    })

    response = client.post("/snaptrade/register", json={"user_id": "vipin"})
    assert response.status_code == 200
    assert response.json() == {"user_secret": "secret123"}

    db = Session(bind=TEST_ENGINE)
    user = db.query(SnaptradeUser).filter(SnaptradeUser.user_id == "vipin").first()
    assert user is not None
    assert user.snaptrade_user_secret == "secret123"
    assert user.snaptrade_user_id == "snap123"
    db.close()


@patch("app.services.snaptrade_service._snaptrade_client")
def test_register_user_duplicate_returns_400(mock_client):
    """Registering the same user_id twice should return 400 (DB unique constraint)."""
    mock_client.authentication.register_snap_trade_user.return_value = MockResponse({
        "userSecret": "secret123",
        "userId": "snap123",
    })
    client.post("/snaptrade/register", json={"user_id": "vipin"})
    response = client.post("/snaptrade/register", json={"user_id": "vipin"})
    assert response.status_code == 400


@patch("app.services.snaptrade_service._snaptrade_client")
def test_register_user_sdk_missing_fields_returns_400(mock_client):
    """If SDK response is missing userSecret, service raises RuntimeError → 400."""
    mock_client.authentication.register_snap_trade_user.return_value = MockResponse({})
    response = client.post("/snaptrade/register", json={"user_id": "vipin"})
    assert response.status_code == 400


# ── /snaptrade/connect ─────────────────────────────────────────────────────────

@patch("app.services.snaptrade_service._snaptrade_client")
def test_get_login_url_success(mock_client):
    db = Session(bind=TEST_ENGINE)
    db.add(SnaptradeUser(user_id="vipin", snaptrade_user_id="suid", snaptrade_user_secret="secret456"))
    db.commit()
    db.close()

    mock_client.authentication.login_snap_trade_user.return_value = MockResponse({
        "redirectURI": "https://snaptrade.com/oauth?code=abc",
    })
    response = client.post("/snaptrade/connect", json={"user_id": "vipin", "broker": "ROBINHOOD"})
    assert response.status_code == 200
    assert response.json() == {"redirect_uri": "https://snaptrade.com/oauth?code=abc"}


def test_connect_user_not_registered_returns_400():
    """Connecting a user that was never registered should return 400."""
    response = client.post("/snaptrade/connect", json={"user_id": "ghost", "broker": "ROBINHOOD"})
    assert response.status_code == 400
    assert "ghost" in response.json()["detail"]


@patch("app.services.snaptrade_service._snaptrade_client")
def test_connect_sdk_missing_redirect_uri_returns_400(mock_client):
    db = Session(bind=TEST_ENGINE)
    db.add(SnaptradeUser(user_id="vipin", snaptrade_user_id="suid", snaptrade_user_secret="s"))
    db.commit()
    db.close()

    mock_client.authentication.login_snap_trade_user.return_value = MockResponse({})
    response = client.post("/snaptrade/connect", json={"user_id": "vipin", "broker": "ROBINHOOD"})
    assert response.status_code == 400


# ── /snaptrade/accounts ────────────────────────────────────────────────────────

@patch("app.services.snaptrade_service._snaptrade_client")
def test_list_accounts_success(mock_client):
    mock_client.account_information.get_user_account_list.return_value = MockResponse({
        "accounts": [
            {"account_id": "acc1", "account_name": "Robinhood", "brokerage": "ROBINHOOD"},
            {"account_id": "acc2", "account_name": "TD Ameritrade", "brokerage": "TDAMERITRADE"},
        ]
    })
    db = Session(bind=TEST_ENGINE)
    db.add(SnaptradeUser(user_id="vipin", snaptrade_user_id="suid", snaptrade_user_secret="s"))
    db.commit()
    db.close()

    response = client.get("/snaptrade/accounts", params={"user_id": "vipin"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["account_id"] == "acc1"
    assert data[1]["brokerage"] == "TDAMERITRADE"


@patch("app.services.snaptrade_service._snaptrade_client")
def test_list_accounts_empty(mock_client):
    mock_client.account_information.get_user_account_list.return_value = MockResponse({"accounts": []})
    db = Session(bind=TEST_ENGINE)
    db.add(SnaptradeUser(user_id="vipin", snaptrade_user_id="suid", snaptrade_user_secret="s"))
    db.commit()
    db.close()

    response = client.get("/snaptrade/accounts", params={"user_id": "vipin"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_accounts_user_not_found_returns_400():
    response = client.get("/snaptrade/accounts", params={"user_id": "ghost"})
    assert response.status_code == 400


# ── /snaptrade/holdings/{account_id} ──────────────────────────────────────────

@patch("app.services.snaptrade_service._snaptrade_client")
def test_get_holdings_success(mock_client):
    mock_client.account_information.get_user_holdings.return_value = MockResponse({
        "positions": [
            {"symbol": {"symbol": "AAPL"}, "units": 10, "price": 150.0, "value": 1500.0},
            {"symbol": {"symbol": "TSLA"}, "units": 5, "price": 800.0, "value": 4000.0},
        ]
    })
    db = Session(bind=TEST_ENGINE)
    db.add(SnaptradeUser(user_id="vipin", snaptrade_user_id="suid", snaptrade_user_secret="s"))
    db.commit()
    db.close()

    response = client.get("/snaptrade/holdings/acc1", params={"user_id": "vipin"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0] == {"symbol": "AAPL", "units": 10.0, "price": 150.0, "value": 1500.0}
    assert data[1] == {"symbol": "TSLA", "units": 5.0, "price": 800.0, "value": 4000.0}


@patch("app.services.snaptrade_service._snaptrade_client")
def test_get_holdings_empty(mock_client):
    mock_client.account_information.get_user_holdings.return_value = MockResponse({"positions": []})
    db = Session(bind=TEST_ENGINE)
    db.add(SnaptradeUser(user_id="vipin", snaptrade_user_id="suid", snaptrade_user_secret="s"))
    db.commit()
    db.close()

    response = client.get("/snaptrade/holdings/acc1", params={"user_id": "vipin"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_holdings_user_not_found_returns_400():
    response = client.get("/snaptrade/holdings/acc1", params={"user_id": "ghost"})
    assert response.status_code == 400
