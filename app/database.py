from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

# SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
