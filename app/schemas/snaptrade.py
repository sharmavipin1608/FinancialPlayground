from pydantic import BaseModel
from typing import List, Optional

class RegisterUserRequest(BaseModel):
    user_id: str

class ConnectBrokerageRequest(BaseModel):
    user_id: str
    broker: str = "ROBINHOOD"

class AccountSchema(BaseModel):
    account_id: str
    account_name: str
    brokerage: str

class HoldingSchema(BaseModel):
    symbol: str
    units: float
    price: float
    value: float
