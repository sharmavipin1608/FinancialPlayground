from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.snaptrade_service import (
    register_user as svc_register_user,
    get_login_url as svc_get_login_url,
    get_accounts as svc_get_accounts,
    get_holdings as svc_get_holdings,
)
from ..schemas.snaptrade import (
    RegisterUserRequest,
    ConnectBrokerageRequest,
    AccountSchema,
    HoldingSchema,
)

router = APIRouter()

@router.post("/register", response_model=dict)
def register(request: RegisterUserRequest, db: Session = Depends(get_db)):
    """Register a SnapTrade user and return the secret token."""
    try:
        secret = svc_register_user(request.user_id, db)
        return {"user_secret": secret}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/connect", response_model=dict)
def connect(request: ConnectBrokerageRequest, db: Session = Depends(get_db)):
    """Generate an OAuth URL for the user to connect a brokerage (Robinhood by default)."""
    try:
        url = svc_get_login_url(request.user_id, db)
        return {"redirect_uri": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/accounts", response_model=List[AccountSchema])
def list_accounts(user_id: str, db: Session = Depends(get_db)):
    """Return all accounts linked to the SnapTrade user."""
    try:
        accounts = svc_get_accounts(user_id, db)
        return accounts
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/holdings/{account_id}", response_model=List[HoldingSchema])
def get_holdings(account_id: str, user_id: str, db: Session = Depends(get_db)):
    """Return holdings for a specific account of the user."""
    try:
        holdings = svc_get_holdings(user_id, account_id, db)
        return holdings
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
