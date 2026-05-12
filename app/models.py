from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class SnaptradeUser(Base):
    __tablename__ = "snaptrade_users"
    user_id = Column(String, primary_key=True, index=True)
    snaptrade_user_id = Column(String, nullable=False)
    snaptrade_user_secret = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TradeLog(Base):
    __tablename__ = "trade_log"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)  # buy or sell
    qty = Column(Float, nullable=False)
    order_type = Column(String, nullable=False)
    limit_price = Column(Float, nullable=True)
    source = Column(String, nullable=False)  # mirror or manual
    alpaca_order_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
