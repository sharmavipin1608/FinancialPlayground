import logging
from typing import List, Dict, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce

from ..config import settings
from ..database import SessionLocal
from ..models import TradeLog

logger = logging.getLogger(__name__)

# Initialise Alpaca client (singleton)
_alpaca_client = TradingClient(
    api_key=settings.ALPACA_API_KEY,
    secret_key=settings.ALPACA_API_SECRET,
    paper=True,
)


def get_account() -> Dict:
    """Return basic account info (equity, cash, buying power)."""
    account = _alpaca_client.get_account()
    # Convert to simple dict (only key fields for now)
    return {
        "equity": getattr(account, "equity", None),
        "cash": getattr(account, "cash", None),
        "buying_power": getattr(account, "buying_power", None),
    }


def get_positions() -> List[Dict]:
    """Return a list of open paper positions."""
    positions = _alpaca_client.get_all_positions()
    result = []
    for p in positions:
        result.append(
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
        )
    return result


def place_order(
    symbol: str,
    qty: float,
    side: str,
    order_type: str = "market",
    limit_price: Optional[float] = None,
    time_in_force: str = "day",
    db=None,
    source: str = "manual",
) -> Dict:
    """Submit an order via Alpaca and log it to ``trade_log``.

    Returns the order details as a dict.
    """
    # Build the appropriate request object
    tif = TimeInForce(time_in_force)
    order_side = AlpacaOrderSide.BUY if side == "buy" else AlpacaOrderSide.SELL

    if order_type == "market":
        order_req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=tif,
        )
    elif order_type == "limit":
        if limit_price is None:
            raise ValueError("limit_price required for limit orders")
        order_req = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            limit_price=limit_price,
            time_in_force=tif,
        )
    else:
        raise ValueError(f"Unsupported order_type: {order_type}")

    order = _alpaca_client.submit_order(order_req)

    # Log to DB if a session is provided
    if db is not None:
        trade = TradeLog(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            source=source,
            alpaca_order_id=getattr(order, "id", ""),
            status=getattr(order, "status", ""),
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

    # Convert order object to dict (basic fields)
    return {
        "id": getattr(order, "id", None),
        "symbol": getattr(order, "symbol", None),
        "qty": float(getattr(order, "qty", 0)),
        "side": getattr(order, "side", None),
        "order_type": getattr(order, "type", None),
        "status": getattr(order, "status", None),
    }


def get_orders(status: str = "all") -> List[Dict]:
    """Retrieve orders filtered by status ("open", "closed", "all")."""
    orders = _alpaca_client.get_orders(
        status=status,
        limit=100,
    )
    result = []
    for o in orders:
        result.append(
            {
                "id": o.id,
                "symbol": o.symbol,
                "qty": float(o.qty),
                "side": o.side,
                "order_type": o.type,
                "status": o.status,
                "filled_at": getattr(o, "filled_at", None),
                "filled_avg_price": getattr(o, "filled_avg_price", None),
            }
        )
    return result


def close_position(symbol: str) -> Dict:
    """Liquidate a position for *symbol* on the paper account."""
    result = _alpaca_client.close_position(symbol)
    # ``close_position`` returns a dict with a ``status`` field in the SDK
    return {"symbol": symbol, "result": result}
