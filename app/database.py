from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/paddio"
)

# Cloud SQL con IP pública suele requerir SSL; si no está en la URL, lo añadimos
if "localhost" not in SQLALCHEMY_DATABASE_URL and "sslmode" not in SQLALCHEMY_DATABASE_URL.lower():
    sep = "&" if "?" in SQLALCHEMY_DATABASE_URL else "?"
    SQLALCHEMY_DATABASE_URL = f"{SQLALCHEMY_DATABASE_URL}{sep}sslmode=require"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Import all models to ensure they are registered with the Base class
from app.models.user import User
from app.models.club import Club
from app.models.court import Court
from app.models.match import Match
from app.models.turn import Turn
from app.models.pregame_turn import PregameTurn
from app.models.booking import Booking

# Note: Tables will be created by Alembic migrations
# Base.metadata.create_all(bind=engine, checkfirst=True)
