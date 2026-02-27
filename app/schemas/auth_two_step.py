from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
from app.enums.user_category import UserCategory


class UserBasicRegistration(BaseModel):
    """Schema para registro básico (Paso 1)"""

    name: str
    last_name: str
    email: EmailStr
    password: str
    gender: str  # Movido al primer paso

    @validator("name", "last_name")
    def validate_names(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Nombre y apellido deben tener al menos 2 caracteres")
        return v.strip()

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v

    @validator("gender")
    def validate_gender(cls, v):
        if v not in ["Masculino", "Femenino"]:
            raise ValueError("Género debe ser: Masculino o Femenino")
        return v


class EmailVerification(BaseModel):
    """Schema para verificación de email"""

    email: EmailStr
    code: str
    temp_token: str

    @validator("code")
    def validate_code(cls, v):
        if not v or len(v) != 5 or not v.isdigit():
            raise ValueError("El código debe ser de 5 dígitos")
        return v


class UserProfileCompletion(BaseModel):
    """Schema para completar perfil (Paso 2)"""

    category: Optional[str] = None
    height: Optional[int] = None
    dominant_hand: Optional[str] = None
    preferred_side: Optional[str] = None
    preferred_court_type: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None

    @validator("category")
    def validate_category(cls, v):
        if v and v not in [
            "9na",
            "8va",
            "7ma",
            "6ta",
            "5ta",
            "4ta",
            "3ra",
            "2da",
            "1ra",
        ]:
            raise ValueError("Categoría inválida")
        return v

    @validator("height")
    def validate_height(cls, v):
        if v and (v < 100 or v > 250):
            raise ValueError("Altura debe estar entre 100 y 250 cm")
        return v

    @validator("dominant_hand")
    def validate_dominant_hand(cls, v):
        if v and v not in ["Izquierda", "Derecha"]:
            raise ValueError("Mano dominante debe ser: Izquierda o Derecha")
        return v

    @validator("preferred_side")
    def validate_preferred_side(cls, v):
        if v and v not in ["Revés", "Drive"]:
            raise ValueError("Lado preferido debe ser: Revés o Drive")
        return v

    @validator("preferred_court_type")
    def validate_preferred_court_type(cls, v):
        if v and v not in ["Cerrada", "Abierta", "Ambas"]:
            raise ValueError(
                "Tipo de cancha preferido debe ser: Cerrada, Abierta o Ambas"
            )
        return v


class ResendCodeRequest(BaseModel):
    """Schema para reenviar código"""

    email: EmailStr


class UserBasicResponse(BaseModel):
    """Respuesta del registro básico"""

    success: bool
    temp_token: str
    message: str


class EmailVerificationResponse(BaseModel):
    """Respuesta de verificación de email"""

    success: bool
    access_token: str
    refresh_token: Optional[str] = None
    user: dict
    message: str


class ProfileCompletionResponse(BaseModel):
    """Respuesta de completar perfil"""

    success: bool
    user: dict
    message: str


class ResendCodeResponse(BaseModel):
    """Respuesta de reenvío de código"""

    success: bool
    message: str


class RefreshTokenRequest(BaseModel):
    """Body para POST /auth/refresh"""

    refresh_token: str
