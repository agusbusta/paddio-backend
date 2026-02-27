from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.models.fcm_token import FCMToken
from app.schemas.fcm_token import FCMTokenCreate, FCMTokenUpdate

logger = logging.getLogger(__name__)


def create_fcm_token(db: Session, token_data: FCMTokenCreate, user_id: int) -> FCMToken:
    """Crear o actualizar un token FCM para un usuario"""
    # Obtener información del usuario para los logs
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    user_email = user.email if user else "unknown"
    user_name = user.name if user else "unknown"
    
    # Token parcial para logs (primeros y últimos caracteres)
    token_preview = f"{token_data.token[:20]}...{token_data.token[-10:]}" if len(token_data.token) > 30 else token_data.token
    
    # Verificar si el token ya existe
    existing_token = db.query(FCMToken).filter(FCMToken.token == token_data.token).first()
    
    if existing_token:
        # Si el token existe pero pertenece a otro usuario, actualizarlo
        if existing_token.user_id != user_id:
            old_user_id = existing_token.user_id
            existing_token.user_id = user_id
            existing_token.device_type = token_data.device_type
            existing_token.is_active = True
            db.commit()
            db.refresh(existing_token)
            logger.info(
                f"🔄 FCM Token actualizado - Token movido del usuario {old_user_id} al usuario {user_id} "
                f"({user_email}) | Device: {token_data.device_type or 'unknown'} | Token: {token_preview}"
            )
            return existing_token
        else:
            # Si el token ya pertenece al usuario, solo actualizar la info
            existing_token.device_type = token_data.device_type
            existing_token.is_active = True
            db.commit()
            db.refresh(existing_token)
            logger.info(
                f"🔄 FCM Token actualizado - Usuario {user_id} ({user_email}) | "
                f"Device: {token_data.device_type or 'unknown'} | Token: {token_preview}"
            )
            return existing_token
    
    # Crear nuevo token
    db_token = FCMToken(
        user_id=user_id,
        token=token_data.token,
        device_type=token_data.device_type,
        is_active=True
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    logger.info(
        f"✅ FCM Token CREADO - Usuario {user_id} ({user_email}, {user_name}) | "
        f"Device: {token_data.device_type or 'unknown'} | Token ID: {db_token.id} | Token: {token_preview}"
    )
    return db_token


def get_user_fcm_tokens(db: Session, user_id: int, active_only: bool = True) -> List[FCMToken]:
    """Obtener todos los tokens FCM de un usuario"""
    query = db.query(FCMToken).filter(FCMToken.user_id == user_id)
    
    if active_only:
        query = query.filter(FCMToken.is_active == True)
    
    return query.all()


def get_fcm_token_by_token(db: Session, token: str) -> Optional[FCMToken]:
    """Obtener un token FCM por su valor"""
    return db.query(FCMToken).filter(FCMToken.token == token).first()


def update_fcm_token(db: Session, token_id: int, token_update: FCMTokenUpdate) -> Optional[FCMToken]:
    """Actualizar un token FCM"""
    db_token = db.query(FCMToken).filter(FCMToken.id == token_id).first()
    
    if not db_token:
        return None
    
    update_data = token_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_token, field, value)
    
    db.commit()
    db.refresh(db_token)
    return db_token


def deactivate_fcm_token(db: Session, token: str) -> bool:
    """Desactivar un token FCM"""
    db_token = db.query(FCMToken).filter(FCMToken.token == token).first()
    
    if not db_token:
        return False
    
    db_token.is_active = False
    db.commit()
    return True


def delete_fcm_token(db: Session, token_id: int) -> bool:
    """Eliminar un token FCM"""
    db_token = db.query(FCMToken).filter(FCMToken.id == token_id).first()
    
    if not db_token:
        return False
    
    db.delete(db_token)
    db.commit()
    return True


def get_fcm_token_by_user_and_token_string(db: Session, user_id: int, token_string: str) -> Optional[FCMToken]:
    """Obtener un token FCM por usuario y string del token"""
    return db.query(FCMToken).filter(
        FCMToken.user_id == user_id,
        FCMToken.token == token_string
    ).first()


def get_active_tokens_for_users(db: Session, user_ids: List[int]) -> List[str]:
    """Obtener todos los tokens activos para una lista de usuarios"""
    tokens = db.query(FCMToken.token).filter(
        FCMToken.user_id.in_(user_ids),
        FCMToken.is_active == True
    ).all()
    
    return [token[0] for token in tokens]
