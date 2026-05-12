import logging
from typing import List, Dict

from snaptrade_client import SnapTrade

from ..config import settings
from ..database import SessionLocal
from ..models import SnaptradeUser

logger = logging.getLogger(__name__)

# Initialise the SnapTrade SDK client (singleton)
_snaptrade_client = SnapTrade(
    client_id=settings.SNAPTRADE_CLIENT_ID,
    consumer_key=settings.SNAPTRADE_CONSUMER_KEY,
)


def _get_user_record(user_id: str, db) -> SnaptradeUser:
    """Fetch the SnaptradeUser row for *user_id* or raise HTTPException."""
    record = db.query(SnaptradeUser).filter(SnaptradeUser.user_id == user_id).first()
    if not record:
        raise ValueError(f"Snaptrade user '{user_id}' not found. Register first.")
    return record


def register_user(user_id: str, db) -> str:
    """Register a new SnapTrade user and store the secret.

    Returns the `snaptrade_user_secret` which will be needed for subsequent calls.
    """
    response = _snaptrade_client.authentication.register_snap_trade_user(
        body={"userId": user_id}
    )
    # Expected response shape per SDK docs
    user_secret = response.body.get("userSecret")
    snaptrade_user_id = response.body.get("userId")
    if not user_secret or not snaptrade_user_id:
        raise RuntimeError("Unexpected response from SnapTrade register endpoint")

    # Persist
    record = SnaptradeUser(
        user_id=user_id,
        snaptrade_user_id=snaptrade_user_id,
        snaptrade_user_secret=user_secret,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("Registered SnapTrade user %s", user_id)
    return user_secret


def get_login_url(user_id: str, db) -> str:
    """Return the OAuth redirect URL for the given *user_id*.

    The user must have been registered first.
    """
    user = _get_user_record(user_id, db)
    response = _snaptrade_client.authentication.login_snap_trade_user(
        body={"userId": user_id, "userSecret": user.snaptrade_user_secret}
    )
    redirect_uri = response.body.get("redirectURI")
    if not redirect_uri:
        raise RuntimeError("Failed to obtain OAuth redirect URL from SnapTrade")
    return redirect_uri


def get_accounts(user_id: str, db) -> List[Dict]:
    """Return a list of accounts linked to the SnapTrade user.

    Each item includes ``account_id``, ``account_name`` and ``brokerage``.
    """
    user = _get_user_record(user_id, db)
    response = _snaptrade_client.account_information.get_user_account_list(
        user_id=user_id,
        user_secret=user.snaptrade_user_secret,
    )
    # SDK returns a dict with ``accounts`` key – adapt as needed
    return response.body.get("accounts", [])


def get_holdings(user_id: str, account_id: str, db) -> List[Dict]:
    """Return normalized holdings for *account_id*.

    Output items contain ``symbol``, ``units``, ``price`` and ``value``.
    """
    user = _get_user_record(user_id, db)
    response = _snaptrade_client.account_information.get_user_holdings(
        account_id=account_id,
        user_id=user_id,
        user_secret=user.snaptrade_user_secret,
    )
    # Expected shape: ``positions`` list of dicts – map to our schema fields
    holdings = []
    for item in response.body.get("positions", []):
        holdings.append(
            {
                "symbol": item.get("symbol", "").get("symbol", ""),
                "units": float(item.get("units", 0)),
                "price": float(item.get("price", 0)),
                "value": float(item.get("value", 0)),
            }
        )
    return holdings
