from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.alpaca_service import (
    get_account as svc_get_account,
    get_positions as svc_get_positions,
    place_order as svc_place_order,
    get_orders as svc_get_orders,
    close_position as svc_close_position,
)
from ..schemas.alpaca import (
    PlaceOrderRequest,
    PositionSchema,
    OrderSchema,
)

router = APIRouter()

@router.get("/account", response_model=dict)
def account_info():
    try:
        return svc_get_account()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions", response_model=list[PositionSchema])
def list_positions():
    try:
        return svc_get_positions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orders", response_model=OrderSchema)
def create_order(request: PlaceOrderRequest, db: Session = Depends(get_db)):
    try:
        order = svc_place_order(
            symbol=request.symbol,
            qty=request.qty,
            side=request.side,
            order_type=request.order_type,
            limit_price=request.limit_price,
            time_in_force=request.time_in_force,
            db=db,
        )
        return order
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orders", response_model=list[OrderSchema])
def list_orders(status: str = "all"):
    try:
        return svc_get_orders(status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/positions/{symbol}", response_model=dict)
def delete_position(symbol: str, db: Session = Depends(get_db)):
    try:
        return svc_close_position(symbol)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
