from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
import logging
import os
from datetime import datetime
from logging.handlers import SMTPHandler
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Configure base logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# Add the parent directory to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.routers import (
    auth,
    users,
    clubs,
    courts,
    matches,
    turns,
    bookings,
    pregame_turns,
)
from app.database import engine, Base, get_db
from app.init_db import create_initial_admins
from app.services.email import email_service
import uvicorn

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize super admin
logger.info("Initializing database with super admin...")
db = next(get_db())
create_initial_admins(db)

app = FastAPI(
    title="Paddio API",
    description="API for managing padel clubs, courts, bookings and matches",
    version="1.0.0",
)


# Configure email error reporting
def _configure_email_error_reporting() -> None:
    enable_emails = os.getenv("ENABLE_ERROR_EMAILS", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    if not enable_emails:
        logger.info(
            "Email error reporting disabled (ENABLE_ERROR_EMAILS not set or false)"
        )
        return

    if not email_service.is_configured():
        logger.warning("Email service not configured: missing SMTP settings")
        return

    logger.info("Email error reporting configured successfully")


_configure_email_error_reporting()

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
app.include_router(courts.router, prefix="/courts", tags=["courts"])
app.include_router(matches.router, prefix="/matches", tags=["matches"])
app.include_router(turns.router, prefix="/turns", tags=["turns"])
app.include_router(
    pregame_turns.router, prefix="/pregame-turns", tags=["pregame-turns"]
)
app.include_router(bookings.router, prefix="/bookings", tags=["bookings"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Paddio API"}


# Endpoint temporal para probar el sistema de emails de error
@app.get("/__test_error")
def test_error():
    """Endpoint temporal para probar el envío de emails de error"""
    raise RuntimeError("SMTP test error - esto debería enviar un email")


# Endpoint para probar credenciales SMTP
@app.get("/__test_smtp")
def test_smtp_credentials():
    """Endpoint para validar configuración SMTP"""
    return email_service.test_connection()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5009, reload=True)


# Global unhandled exception handler -> logs ERROR and sends email
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    try:
        # Log the error
        logger.exception(
            "Unhandled error | path=%s | method=%s | client=%s",
            request.url.path,
            request.method,
            request.client.host if request.client else "unknown",
        )

        # Send error email if configured
        if email_service.is_configured():
            error_data = {
                "path": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else "unknown",
                "user": getattr(request.state, "user_email", "Anonymous"),
                "exception": exc,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
            email_service.send_error_email(error_data)

    finally:
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )
