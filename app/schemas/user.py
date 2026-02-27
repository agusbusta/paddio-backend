from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.enums.user_category import UserCategory


class UserBase(BaseModel):
    name: str
    last_name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str
    category: Optional[UserCategory] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    category: Optional[UserCategory] = None
    # Campos del perfil deportivo
    gender: Optional[str] = None
    height: Optional[int] = None
    dominant_hand: Optional[str] = None
    preferred_side: Optional[str] = None
    preferred_court_type: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    # Campos adicionales
    profile_image_url: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Juan Pérez",
                "last_name": "García",
                "email": "juan@email.com",
                "phone": "+1234567890",
                "category": "5ta",
                "gender": "Masculino",
                "height": 175,
                "dominant_hand": "Derecha",
                "preferred_side": "DRIVE",
                "preferred_court_type": "Indoor",
                "city": "Buenos Aires",
                "province": "CABA",
                "profile_image_url": "https://example.com/photo.jpg",
                "level": "Intermedio",
                "location": "Palermo",
            }
        }


class UserRating(BaseModel):
    rating: float
    comment: Optional[str] = None


class UserInDB(UserBase):
    id: int
    last_name: Optional[str] = None
    overall_rating: Optional[float] = 0.0
    created_at: datetime
    is_active: bool = True
    is_admin: Optional[bool] = False
    is_super_admin: Optional[bool] = False
    category: Optional[str] = None
    # Campos del perfil deportivo
    gender: Optional[str] = None
    height: Optional[int] = None
    dominant_hand: Optional[str] = None
    preferred_side: Optional[str] = None
    preferred_court_type: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    # Estados del usuario
    is_profile_complete: Optional[bool] = False
    # Campos adicionales
    profile_image_url: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    pass


class UserChangePassword(BaseModel):
    current_password: str
    new_password: str

    class Config:
        schema_extra = {
            "example": {
                "current_password": "old_password123",
                "new_password": "new_secure_password456",
            }
        }


class AdminBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    club_id: Optional[int] = None


class AdminCreate(AdminBase):
    password: str


class AdminUpdate(AdminBase):
    is_active: bool


class AdminSchema(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    club_id: Optional[int] = None
    club_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    role: str = "admin"

    class Config:
        from_attributes = True


class AdminResponse(BaseModel):
    admin: AdminSchema


class AdminsResponse(BaseModel):
    admins: List[AdminSchema]
