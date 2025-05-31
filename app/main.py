from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.routers import auth, users, clubs, stadiums, courts, matches, turns, bookings
from app.database import engine, Base, get_db
from app.init_db import create_initial_admins
import uvicorn

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize super admin
logger.info("Initializing database with super admin...")
db = next(get_db())
create_initial_admins(db)

app = FastAPI(
    title="Paddio API",
    description="API for managing padel court bookings and matches",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(clubs.router, prefix="/clubs", tags=["clubs"])
app.include_router(stadiums.router, prefix="/stadiums", tags=["stadiums"])
app.include_router(courts.router, prefix="/courts", tags=["courts"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(turns.router, prefix="/turns", tags=["turns"])
app.include_router(bookings.router, prefix="/bookings", tags=["bookings"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Paddio API"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5009, reload=True)
