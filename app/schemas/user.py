from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None


class UserRating(BaseModel):
    rating: float
    comment: Optional[str] = None


class UserInDB(UserBase):
    id: int
    overall_rating: Optional[float] = 0.0
    created_at: datetime
    is_active: bool = True
    is_admin: bool = False
    is_super_admin: bool = False

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
