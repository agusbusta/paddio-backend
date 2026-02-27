from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserFavoriteClubBase(BaseModel):
    user_id: int
    club_id: int


class UserFavoriteClubCreate(UserFavoriteClubBase):
    pass


class UserFavoriteClubInDB(UserFavoriteClubBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserFavoriteClubResponse(UserFavoriteClubInDB):
    pass


class ClubFavoriteInfo(BaseModel):
    """Información del club para mostrar en favoritos"""

    club_id: int
    club_name: str
    club_address: str
    club_phone: str
    added_to_favorites_at: datetime

    class Config:
        from_attributes = True
