from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.crud import user_favorite_club as favorite_crud
from app.schemas.user_favorite_club import UserFavoriteClubCreate, ClubFavoriteInfo

router = APIRouter()


@router.post("/favorite-clubs/{club_id}")
def add_club_to_favorites(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Agregar un club a los favoritos del usuario actual.
    """
    # Verificar que el usuario sea un jugador (no admin ni super admin)
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only players can manage favorite clubs"
        )

    # Verificar que el club existe
    from app.crud import club as club_crud

    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Verificar si ya es favorito
    existing_favorite = favorite_crud.get_user_favorite_club(
        db, current_user.id, club_id
    )
    if existing_favorite:
        raise HTTPException(status_code=400, detail="Club already in favorites")

    # Crear la relación de favorito
    favorite_data = UserFavoriteClubCreate(user_id=current_user.id, club_id=club_id)

    favorite_club = favorite_crud.create_user_favorite_club(db, favorite_data)

    return {
        "message": "Club added to favorites successfully",
        "club_id": club_id,
        "club_name": club.name,
    }


@router.delete("/favorite-clubs/{club_id}")
def remove_club_from_favorites(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Quitar un club de los favoritos del usuario actual.
    """
    # Verificar que el usuario sea un jugador (no admin ni super admin)
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only players can manage favorite clubs"
        )

    # Verificar que el club existe
    from app.crud import club as club_crud

    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Eliminar de favoritos
    success = favorite_crud.delete_user_favorite_club(db, current_user.id, club_id)
    if not success:
        raise HTTPException(status_code=404, detail="Club not in favorites")

    return {
        "message": "Club removed from favorites successfully",
        "club_id": club_id,
        "club_name": club.name,
    }


@router.get("/favorite-clubs")
def get_user_favorite_clubs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener todos los clubs favoritos del usuario actual.
    """
    # Verificar que el usuario sea un jugador (no admin ni super admin)
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only players can view favorite clubs"
        )

    # Obtener clubs favoritos
    favorite_clubs = favorite_crud.get_user_favorite_clubs(db, current_user.id)

    # Formatear la respuesta con información del club
    clubs_info = []
    for fav in favorite_clubs:
        clubs_info.append(
            ClubFavoriteInfo(
                club_id=fav.club.id,
                club_name=fav.club.name,
                club_address=fav.club.address,
                club_phone=fav.club.phone,
                added_to_favorites_at=fav.created_at,
            )
        )

    return {
        "user_id": current_user.id,
        "total_favorites": len(clubs_info),
        "favorite_clubs": clubs_info,
    }


@router.get("/favorite-clubs/check/{club_id}")
def check_if_club_is_favorite(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verificar si un club específico está en los favoritos del usuario.
    """
    # Verificar que el usuario sea un jugador (no admin ni super admin)
    if current_user.is_admin or current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only players can check favorite clubs"
        )

    # Verificar que el club existe
    from app.crud import club as club_crud

    club = club_crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Verificar si es favorito
    is_favorite = (
        favorite_crud.get_user_favorite_club(db, current_user.id, club_id) is not None
    )

    return {"club_id": club_id, "club_name": club.name, "is_favorite": is_favorite}
