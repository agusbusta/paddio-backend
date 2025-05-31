from sqlalchemy.orm import Session
from app.models.user import User
from app.services.auth import get_password_hash
import logging

logger = logging.getLogger(__name__)


def create_initial_admins(db: Session):
    """
    Crea los dos usuarios admin predefinidos si la tabla está vacía.
    """
    if db.query(User).count() > 0:
        logger.info("Ya existen usuarios, no se crean admins iniciales.")
        return

    users_data = [
        {
            "name": "adminagus",
            "email": "adminagus@paddio.com",
            "password": "password.Ab",
        },
        {
            "name": "adminmaxi",
            "email": "adminmaxi@paddio.com",
            "password": "password.Ml",
        },
    ]

    for user in users_data:
        hashed_password = get_password_hash(user["password"])
        db_user = User(
            name=user["name"],
            email=user["email"],
            phone=None,
            hashed_password=hashed_password,
            is_admin=True,
            is_super_admin=True,
            is_active=True,
        )
        db.add(db_user)
        logger.info(f"Admin creado: {user['email']}")

    db.commit()
