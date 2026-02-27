from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
import sys
import traceback
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
    user_favorites,
    notifications,
    invitations,
    players,
    fcm_compat,
    georef,
)
from app.database import engine, Base, get_db
from app.init_db import create_initial_admins
from app.services.email import email_service

# Import all models to ensure they are registered with SQLAlchemy
from app.models import user, club, court, match, turn, booking, pregame_turn
from app.models.fcm_token import FCMToken
from app.models.user_favorite_club import UserFavoriteClub
from app.models.notification import Notification
from app.models.invitation import Invitation
from app.models.turn_chat_message import TurnChatMessage
from app.models.turn_chat_read import TurnChatRead

import uvicorn

# Estado de la DB (se llena en lifespan); si falla el init, el worker igual arranca y el error se ve en logs
_db_init_ok = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializar DB al arrancar; si falla, logueamos el error completo para verlo en Cloud Run."""
    global _db_init_ok
    try:
        logger.info("Iniciando DB: create_all...")
        Base.metadata.create_all(bind=engine)
        logger.info("Iniciando DB: create_initial_admins...")
        db = next(get_db())
        create_initial_admins(db)
        _db_init_ok = True
        logger.info("Database init OK")
    except Exception as e:
        # Forzar salida a stderr para que aparezca en Cloud Logging
        tb = traceback.format_exc()
        logger.exception("ERROR en init DB: %s", e)
        print(f"[PADDIO] ERROR en init DB:\n{tb}", file=sys.stderr, flush=True)
        sys.stderr.flush()
        _db_init_ok = False
    yield
    # shutdown si hace falta
    pass


app = FastAPI(
    title="Paddio API",
    description="API for managing padel clubs, courts, bookings and matches",
    version="1.0.0",
    lifespan=lifespan,
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


# Middleware para loggear requests de FCM token
class FCMTokenLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if request.url.path == "/notifications/register-token" and request.method == "POST":
            logger.info(
                f"🔍 [FCM TOKEN] Request detectada - Path: {request.url.path} | "
                f"Method: {request.method} | Client: {request.client.host if request.client else 'unknown'}"
            )
            try:
                # Intentar leer el body (solo para logging, no lo consumimos)
                body = await request.body()
                logger.info(
                    f"📦 [FCM TOKEN] Body recibido: {body.decode('utf-8')[:200]}..." if len(body) > 200 else f"📦 [FCM TOKEN] Body recibido: {body.decode('utf-8')}"
                )
                # Reconstruir el request con el body
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.warning(f"⚠️ [FCM TOKEN] No se pudo leer el body: {e}")
        
        response = await call_next(request)
        
        if request.url.path == "/notifications/register-token" and request.method == "POST":
            logger.info(
                f"📤 [FCM TOKEN] Response enviada - Status: {response.status_code}"
            )
        
        return response


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add FCM token logging middleware (after CORS)
app.add_middleware(FCMTokenLoggingMiddleware)

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
app.include_router(user_favorites.router, prefix="/favorites", tags=["user-favorites"])
app.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
app.include_router(invitations.router, prefix="/invitations", tags=["invitations"])
app.include_router(players.router, prefix="/players", tags=["players"])
app.include_router(georef.router, prefix="/georef", tags=["georef"])
app.include_router(fcm_compat.router, tags=["fcm-compat"])


@app.get("/")
def read_root():
    if not _db_init_ok:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database not initialized; check Cloud Run logs for the startup error."},
        )
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
