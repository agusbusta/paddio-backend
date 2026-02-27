from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CreateInvitationRequest(BaseModel):
    turn_id: int
    invited_player_ids: List[int]
    message: Optional[str] = None


class RespondToInvitationRequest(BaseModel):
    status: str  # "ACCEPTED" | "DECLINED"
    player_side: Optional[str] = None  # "reves" | "drive"
    player_court_position: Optional[str] = None  # "izquierda" | "derecha"


class InvitationBase(BaseModel):
    turn_id: int
    inviter_id: int
    invited_player_id: int
    status: str = "PENDING"
    message: Optional[str] = None
    is_validated_invitation: bool = False  # Marca si viene de un jugador validado
    is_external_request: bool = (
        False  # Marca si es una solicitud externa (requiere aprobación)
    )


class InvitationCreate(InvitationBase):
    pass


class InvitationUpdate(BaseModel):
    status: Optional[str] = None
    message: Optional[str] = None
    responded_at: Optional[datetime] = None
    inviter_id: Optional[int] = (
        None  # Para actualizar cuando se aprueba una solicitud externa
    )
    is_external_request: Optional[bool] = (
        None  # Para marcar cuando se convierte en invitación normal
    )


class InvitationInDB(InvitationBase):
    id: int
    created_at: datetime
    responded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InvitationResponse(BaseModel):
    id: int
    turn_id: int
    inviter_id: int
    inviter_name: str
    inviter_last_name: Optional[str] = None
    invited_player_id: int
    invited_player_name: str
    invited_player_last_name: Optional[str] = None
    status: str
    created_at: datetime
    responded_at: Optional[datetime]
    message: Optional[str]
    club_name: str
    court_name: str
    turn_date: str
    turn_time: str
    price: int
    is_indoor: bool
    has_lighting: bool
    invited_player_gender: Optional[str] = (
        None  # Género del jugador invitado para validación de partidos mixtos
    )
    is_external_request: bool = (
        False  # Marca si es una solicitud externa (requiere aprobación)
    )
    turn_cancellation_message: Optional[str] = (
        None  # Mensaje de cancelación del organizador si el turno fue cancelado
    )
    # Configuración del partido (para mostrar en tarjeta y detalle)
    is_mixed_match: bool = False
    category_restricted: bool = False
    category_restriction_type: Optional[str] = None
    organizer_category: Optional[str] = None
    free_category: Optional[str] = None


class PlayerSearchResponse(BaseModel):
    id: int
    name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    level: str  # BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
    preferred_side: str  # DRIVE, REVES
    location: Optional[str] = None
    category: Optional[str] = None  # 9na, 8va, 7ma, 6ta, 5ta, 4ta, 3ra, 2da, 1ra
    gender: Optional[str] = None  # Masculino, Femenino, Otro


class InvitationsListResponse(BaseModel):
    success: bool
    invitations: List[InvitationResponse]
    total_count: int
