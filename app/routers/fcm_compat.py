from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.crud import fcm_token as fcm_crud
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.delete("/fcm/remove-token", status_code=status.HTTP_200_OK)
def remove_fcm_token_compat(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Eliminar un token FCM por el token string (compatibilidad con frontend).
    Este endpoint mantiene compatibilidad con la URL que espera el frontend.
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
