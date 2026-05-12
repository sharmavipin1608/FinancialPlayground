from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Literal

class PlaceOrderRequest(BaseModel):
    symbol: str
    qty: float
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"] = "market"
    limit_price: Optional[float] = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"

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
    qty: float
    side: str
    order_type: str
    status: str
    filled_at: Optional[datetime] = None
    filled_avg_price: Optional[float] = None
