from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from pydantic import BaseModel

from app.database import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.schemas.fcm_token import (
    FCMTokenCreate,
    FCMTokenResponse,
    NotificationRequest,
    NotificationResponse,
)
from app.schemas.notification import (
    NotificationsListResponse,
    NotificationActionResponse,
    NotificationResponse as NotificationResponseSchema,
)
from app.models.notification import Notification
from app.crud import fcm_token as fcm_crud
from app.crud import notification as notification_crud
from app.crud import user as user_crud
from app.services.fcm_service import fcm_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/register-token",
    response_model=FCMTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_fcm_token(
    token_data: FCMTokenCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registrar un token FCM para el usuario actual.

    El frontend debe llamar este endpoint cuando:
    - La app se abre por primera vez
    - El token FCM cambia
    - El usuario hace login
    """
    try:
        # Log de request recibida (antes de cualquier validación)
        token_preview = (
            f"{token_data.token[:20]}...{token_data.token[-10:]}"
            if len(token_data.token) > 30
            else token_data.token[:30]
        )
        logger.info(
            f"📱 [FCM TOKEN] Request recibida - Usuario {current_user.id} ({current_user.email}) | "
            f"Device: {token_data.device_type or 'unknown'} | Token: {token_preview}"
        )

        fcm_token = fcm_crud.create_fcm_token(db, token_data, current_user.id)
        logger.info(
            f"✅ [FCM TOKEN] Token registrado exitosamente - Usuario {current_user.id} | Token ID: {fcm_token.id}"
        )
        return fcm_token
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
    except Exception as e:
        logger.error(
            f"❌ [FCM TOKEN] Error registrando token - Usuario {current_user.id if current_user else 'unknown'} ({current_user.email if current_user else 'unknown'}): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register FCM token",
        )


@router.get("/tokens", response_model=List[FCMTokenResponse])
def get_my_fcm_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtener todos los tokens FCM del usuario actual"""
    tokens = fcm_crud.get_user_fcm_tokens(db, current_user.id)
    return tokens


@router.delete("/tokens/{token_id}", status_code=status.HTTP_200_OK)
def delete_fcm_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Eliminar un token FCM específico"""
    success = fcm_crud.delete_fcm_token(db, token_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="FCM token not found"
        )

    return {"message": "FCM token deleted successfully"}


@router.delete("/fcm/remove-token", status_code=status.HTTP_200_OK)
def remove_fcm_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Eliminar un token FCM por el token string (compatibilidad con frontend).
    """
    try:
        # Buscar el token por el string del token
        fcm_token = fcm_crud.get_fcm_token_by_user_and_token_string(
            db, current_user.id, token
        )
        if not fcm_token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="FCM token not found"
            )

        # Eliminar el token
        success = fcm_crud.delete_fcm_token(db, fcm_token.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete FCM token",
            )

        return {"message": "FCM token removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing FCM token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove FCM token",
        )


@router.post("/test", response_model=NotificationResponse)
def test_notification(
    notification: NotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enviar una notificación de prueba al usuario actual.

    Solo para testing - enviará la notificación a todos los tokens activos del usuario.
    """
    if not fcm_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FCM service not configured",
        )

    # Obtener tokens del usuario
    user_tokens = fcm_crud.get_user_fcm_tokens(db, current_user.id)

    if not user_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No FCM tokens found for user"
        )

    # Preparar datos de la notificación
    data = notification.data or {}
    data.update({"type": "test", "user_id": str(current_user.id)})

    # Enviar notificación
    tokens = [token.token for token in user_tokens]
    result = fcm_service.send_notification_to_multiple_tokens(
        tokens=tokens, title=notification.title, body=notification.body, data=data
    )

    return NotificationResponse(
        success=result["success"] > 0,
        message=f"Sent {result['success']} notifications, {result['failure']} failed",
        sent_count=result["success"],
        failed_count=result["failure"],
    )


@router.get("/status")
def get_notification_status():
    """Verificar el estado del servicio de notificaciones"""
    status_info = fcm_service.test_connection()

    if status_info["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=status_info["message"],
        )

    return status_info


# Endpoints para administradores (solo super admins)
@router.post("/send-to-user/{user_id}", response_model=NotificationResponse)
def send_notification_to_user(
    user_id: int,
    notification: NotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enviar notificación a un usuario específico.

    Solo disponible para super admins.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can send notifications to specific users",
        )

    if not fcm_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FCM service not configured",
        )

    # Obtener tokens del usuario objetivo
    user_tokens = fcm_crud.get_user_fcm_tokens(db, user_id)

    if not user_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FCM tokens found for target user",
        )

    # Preparar datos de la notificación
    data = notification.data or {}
    data.update({"type": "admin_notification", "from_admin": str(current_user.id)})

    # Enviar notificación
    tokens = [token.token for token in user_tokens]
    result = fcm_service.send_notification_to_multiple_tokens(
        tokens=tokens, title=notification.title, body=notification.body, data=data
    )

    return NotificationResponse(
        success=result["success"] > 0,
        message=f"Sent {result['success']} notifications to user {user_id}, {result['failure']} failed",
        sent_count=result["success"],
        failed_count=result["failure"],
    )


@router.post("/send-broadcast", response_model=NotificationResponse)
def send_broadcast_notification(
    notification: NotificationRequest,
    category: Optional[str] = None,
    only_active_users: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enviar notificación masiva a usuarios.
    
    Solo disponible para super admins.
    
    Parámetros:
    - category: Filtrar por categoría de usuario (opcional)
    - only_active_users: Solo enviar a usuarios activos (default: True)
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can send broadcast notifications",
        )

    if not fcm_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FCM service not configured",
        )

    # Obtener usuarios según filtros
    users_query = db.query(User).filter(
        User.is_admin == False,
        User.is_super_admin == False
    )
    
    if only_active_users:
        users_query = users_query.filter(User.is_active == True)
    
    if category:
        users_query = users_query.filter(User.category == category)
    
    target_users = users_query.all()
    
    if not target_users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No users found matching the criteria",
        )

    # Obtener todos los tokens de los usuarios objetivo
    all_tokens = []
    users_with_tokens = 0
    
    for user in target_users:
        user_tokens = fcm_crud.get_user_fcm_tokens(db, user.id)
        if user_tokens:
            all_tokens.extend([token.token for token in user_tokens])
            users_with_tokens += 1

    if not all_tokens:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FCM tokens found for target users",
        )

    # Preparar datos de la notificación
    data = notification.data or {}
    data.update({
        "type": "broadcast_notification",
        "from_admin": str(current_user.id),
        "category": category or "all"
    })

    # Enviar notificación a todos los tokens
    result = fcm_service.send_notification_to_multiple_tokens(
        tokens=all_tokens,
        title=notification.title,
        body=notification.body,
        data=data
    )

    # Guardar registro del historial de notificación masiva
    # Usamos el user_id del super admin que envía para poder filtrar después
    try:
        from app.schemas.notification import NotificationCreate
        broadcast_log = NotificationCreate(
            user_id=current_user.id,  # ID del super admin que envía
            title=notification.title,
            message=notification.body,
            type="broadcast_notification",
            data={
                "from_admin": str(current_user.id),
                "admin_name": current_user.name,
                "category": category or "all",
                "only_active_users": only_active_users,
                "target_users_count": len(target_users),
                "users_with_tokens": users_with_tokens,
                "sent_count": result["success"],
                "failed_count": result["failure"],
            }
        )
        notification_crud.create_notification(db, broadcast_log)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving broadcast notification log: {e}")
        # No fallar el envío si falla el guardado del log

    return NotificationResponse(
        success=result["success"] > 0,
        message=f"Sent {result['success']} notifications to {users_with_tokens} users ({len(target_users)} total), {result['failure']} failed",
        sent_count=result["success"],
        failed_count=result["failure"],
    )


# ===== ENDPOINTS DE NOTIFICACIONES EN BASE DE DATOS =====


@router.get("/", response_model=NotificationsListResponse)
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener todas las notificaciones del usuario actual.

    Retorna:
    - Lista de notificaciones ordenadas por fecha (más recientes primero)
    - Contador de notificaciones no leídas
    """
    try:
        notifications = notification_crud.get_user_notifications(db, current_user.id)
        unread_count = notification_crud.get_unread_notifications_count(
            db, current_user.id
        )

        return NotificationsListResponse(
            success=True, notifications=notifications, unread_count=unread_count
        )
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notifications",
        )


@router.put("/{notification_id}/read", response_model=NotificationActionResponse)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marcar una notificación específica como leída.
    """
    try:
        success = notification_crud.mark_notification_as_read(
            db, notification_id, current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificación no encontrada",
            )

        return NotificationActionResponse(
            success=True, message="Notificación marcada como leída"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read",
        )


@router.put("/read-all", response_model=NotificationActionResponse)
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marcar todas las notificaciones del usuario como leídas.
    """
    try:
        updated_count = notification_crud.mark_all_notifications_as_read(
            db, current_user.id
        )

        return NotificationActionResponse(
            success=True,
            message=f"Todas las notificaciones marcadas como leídas ({updated_count} actualizadas)",
        )
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all notifications as read",
        )


@router.get("/broadcast-history", response_model=List[NotificationResponseSchema])
def get_broadcast_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener historial de notificaciones masivas enviadas.
    
    Solo disponible para super admins.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can view broadcast history",
        )

    # Obtener todas las notificaciones de tipo broadcast_notification
    # Ordenadas por fecha (más recientes primero)
    notifications = (
        db.query(Notification)
        .filter(Notification.type == "broadcast_notification")
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [NotificationResponseSchema.model_validate(n) for n in notifications]


@router.delete("/{notification_id}", response_model=NotificationActionResponse)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Eliminar una notificación específica.
    """
    try:
        success = notification_crud.delete_notification(
            db, notification_id, current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificación no encontrada",
            )

        return NotificationActionResponse(
            success=True, message="Notificación eliminada"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification",
        )


# Endpoint para recibir logs de debug del frontend (especialmente útil para TestFlight)
class DebugLogRequest(BaseModel):
    level: str  # "info", "warning", "error"
    tag: str  # "[FCM]", "[AUTH]", etc.
    message: str
    timestamp: Optional[str] = None


@router.post("/debug-log")
def receive_debug_log(
    log_data: DebugLogRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint para recibir logs de debug del frontend.
    DESHABILITADO: Ya no se procesan logs de debug para reducir requests innecesarios.
    Solo se mantiene el endpoint para compatibilidad con versiones antiguas de la app.
    """
    # Endpoint deshabilitado - no procesar logs para reducir requests
    # Las versiones nuevas de la app no envían logs de debug
    return {"success": True, "message": "Log endpoint disabled"}
