from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.models.user_favorite_club import UserFavoriteClub
from app.schemas.user_favorite_club import UserFavoriteClubCreate


def create_user_favorite_club(
    db: Session, favorite_club: UserFavoriteClubCreate
) -> UserFavoriteClub:
    """Crear una nueva relación de club favorito para un usuario"""
    db_favorite = UserFavoriteClub(**favorite_club.dict())
    db.add(db_favorite)
    db.commit()
    db.refresh(db_favorite)
    return db_favorite


def get_user_favorite_clubs(db: Session, user_id: int) -> List[UserFavoriteClub]:
    """Obtener todos los clubs favoritos de un usuario"""
    return db.query(UserFavoriteClub).filter(UserFavoriteClub.user_id == user_id).all()


def get_user_favorite_club(
    db: Session, user_id: int, club_id: int
) -> Optional[UserFavoriteClub]:
    """Verificar si un club específico es favorito de un usuario"""
    return (
        db.query(UserFavoriteClub)
        .filter(
            and_(
                UserFavoriteClub.user_id == user_id, UserFavoriteClub.club_id == club_id
            )
        )
        .first()
    )


def delete_user_favorite_club(db: Session, user_id: int, club_id: int) -> bool:
    """Eliminar un club de los favoritos de un usuario"""
    favorite_club = get_user_favorite_club(db, user_id, club_id)
    if favorite_club:
        db.delete(favorite_club)
        db.commit()
        return True
    return False


def get_user_favorite_club_ids(db: Session, user_id: int) -> List[int]:
    """Obtener solo los IDs de los clubs favoritos de un usuario"""
    favorites = (
        db.query(UserFavoriteClub.club_id)
        .filter(UserFavoriteClub.user_id == user_id)
        .all()
    )
    return [fav.club_id for fav in favorites]
