import secrets
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.models.user import User
from app.services.auth import get_password_hash

logger = logging.getLogger(__name__)


def generate_verification_code() -> str:
    """Genera un código de verificación de 5 dígitos"""
    return "".join(secrets.choice(string.digits) for _ in range(5))


def generate_temp_token() -> str:
    """Genera un token temporal único"""
    return secrets.token_urlsafe(32)


def create_user_basic(
    db: Session, name: str, last_name: str, email: str, password: str, gender: str
) -> User:
    """
    Crea un usuario básico en estado pendiente de verificación

    Args:
        db: Sesión de base de datos
        name: Nombre del usuario
        last_name: Apellido del usuario
        email: Email del usuario
        password: Contraseña en texto plano
        gender: Género del usuario

    Returns:
        User: Usuario creado
    """
    verification_code = generate_verification_code()
    temp_token = generate_temp_token()

    user = User(
        name=name,
        last_name=last_name,
        email=email,
        hashed_password=get_password_hash(password),
        gender=gender,  # Incluir género en el primer paso
        is_active=False,  # Pendiente de verificación
        is_profile_complete=False,
        verification_code=verification_code,
        temp_token=temp_token,
        created_at=datetime.utcnow(),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Usuario básico creado: {email}")
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Obtiene un usuario por email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_email_and_code(db: Session, email: str, code: str) -> Optional[User]:
    """Obtiene un usuario por email y código de verificación"""
    return (
        db.query(User)
        .filter(User.email == email, User.verification_code == code)
        .first()
    )


def activate_user(db: Session, user_id: int) -> bool:
    """
    Activa un usuario después de verificar el email

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario

    Returns:
        bool: True si se activó exitosamente
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        user.is_active = True
        user.verification_code = None  # Limpiar código usado
        user.temp_token = None  # Limpiar token temporal
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        logger.info(f"Usuario activado: {user.email}")
        return True

    except Exception as e:
        logger.error(f"Error activando usuario {user_id}: {e}")
        db.rollback()
        return False


def update_verification_code(db: Session, user_id: int) -> Optional[str]:
    """
    Actualiza el código de verificación de un usuario

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario

    Returns:
        str: Nuevo código de verificación o None si hay error
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        new_code = generate_verification_code()
        user.verification_code = new_code
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        logger.info(f"Código de verificación actualizado para: {user.email}")
        return new_code

    except Exception as e:
        logger.error(
            f"Error actualizando código de verificación para usuario {user_id}: {e}"
        )
        db.rollback()
        return None


def complete_user_profile(
    db: Session, user_id: int, profile_data: dict
) -> Optional[User]:
    """
    Completa el perfil de un usuario

    Args:
        db: Sesión de base de datos
        user_id: ID del usuario
        profile_data: Datos del perfil

    Returns:
        User: Usuario actualizado o None si hay error
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        # Actualizar campos del perfil
        for field, value in profile_data.items():
            if hasattr(user, field) and value is not None:
                setattr(user, field, value)

        # Calcular is_profile_complete usando la función común
        # UNA SOLA FUENTE DE VERDAD para el cálculo de completitud
        from app.utils.profile_utils import calculate_profile_completeness

        user.is_profile_complete = calculate_profile_completeness(user)
        user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(user)

        logger.info(f"Perfil completado para: {user.email}")
        return user

    except Exception as e:
        logger.error(f"Error completando perfil para usuario {user_id}: {e}")
        db.rollback()
        return None


def is_verification_code_expired(user: User) -> bool:
    """
    Verifica si el código de verificación ha expirado

    Args:
        user: Usuario con código de verificación

    Returns:
        bool: True si el código ha expirado
    """
    if not user.created_at:
        return True

    # Los códigos expiran en 15 minutos
    expiration_time = user.created_at + timedelta(minutes=15)
    return datetime.utcnow() > expiration_time
