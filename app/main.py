import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .database import engine
from .models import Base
from .routers import snaptrade, alpaca, portfolio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    yield


app = FastAPI(title="FinancialPlayground API", lifespan=lifespan)

# Register routers
app.include_router(snaptrade.router, prefix="/snaptrade", tags=["snaptrade"])
app.include_router(alpaca.router, prefix="/alpaca", tags=["alpaca"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
