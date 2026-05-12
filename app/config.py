from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    SNAPTRADE_CLIENT_ID: str
    SNAPTRADE_CONSUMER_KEY: str
    ALPACA_API_KEY: str
    ALPACA_API_SECRET: str
    DATABASE_URL: str = "sqlite:///./financial_playground.db"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

# Create a singleton settings instance for import elsewhere
settings = Settings()
