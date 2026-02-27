from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum
from app.enums.category_restriction import CategoryRestrictionType


class PregameTurnStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PENDING = "PENDING"
    READY_TO_PLAY = "READY_TO_PLAY"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PregameTurnBase(BaseModel):
    turn_id: int
    court_id: int
    selected_court_id: Optional[int] = None
    date: datetime
    start_time: str  # Formato "HH:MM"
    end_time: str  # Formato "HH:MM"
    price: int  # Precio en centavos
    status: PregameTurnStatus = PregameTurnStatus.AVAILABLE
    player1_id: Optional[int] = None
    player2_id: Optional[int] = None
    player3_id: Optional[int] = None
    player4_id: Optional[int] = None
    player1_side: Optional[str] = None  # "reves" o "drive"
    player1_court_position: Optional[str] = None  # "izquierda" o "derecha"
    player2_side: Optional[str] = None
    player2_court_position: Optional[str] = None
    player3_side: Optional[str] = None
    player3_court_position: Optional[str] = None
    player4_side: Optional[str] = None
    player4_court_position: Optional[str] = None
    # Restricciones de categoría
    category_restricted: Optional[bool] = False
    category_restriction_type: Optional[CategoryRestrictionType] = (
        CategoryRestrictionType.NONE
    )
    organizer_category: Optional[str] = None
    # Campos para partidos mixtos
    is_mixed_match: Optional[bool] = False
    free_category: Optional[str] = None


class PregameTurnCreate(PregameTurnBase):
    pass


class PregameTurnUpdate(BaseModel):
    status: Optional[PregameTurnStatus] = None
    selected_court_id: Optional[int] = None
    court_id: Optional[int] = None  # Gestión club: cambio de cancha
    start_time: Optional[str] = None  # Gestión club: cambio de horario (HH:MM)
    player1_id: Optional[int] = None  # None para cancelar posición
    player2_id: Optional[int] = None
    player3_id: Optional[int] = None
    player4_id: Optional[int] = None
    player1_side: Optional[str] = None
    player1_court_position: Optional[str] = None
    player2_side: Optional[str] = None
    player2_court_position: Optional[str] = None
    player3_side: Optional[str] = None
    player3_court_position: Optional[str] = None
    player4_side: Optional[str] = None
    player4_court_position: Optional[str] = None
    # Restricciones de categoría
    category_restricted: Optional[bool] = None
    category_restriction_type: Optional[CategoryRestrictionType] = None
    organizer_category: Optional[str] = None
    # Campos para partidos mixtos
    is_mixed_match: Optional[bool] = None
    free_category: Optional[str] = None
    # Mensaje de justificación para cancelación (solo para cancelaciones individuales)
    cancellation_message: Optional[str] = None


class PregameTurnInDB(PregameTurnBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PregameTurnResponse(PregameTurnInDB):
    pass


class TurnDataItem(BaseModel):
    court_id: int
    court_name: str
    start_time: str  # Formato "HH:MM"
    end_time: str  # Formato "HH:MM"
    price: int  # Precio en centavos


class TurnData(BaseModel):
    club_id: int
    club_name: str
    turns: List[TurnDataItem]


class TurnBase(BaseModel):
    club_id: int
    turns_data: TurnData


class TurnCreate(TurnBase):
    pass


class TurnUpdate(BaseModel):
    turns_data: Optional[TurnData] = None


class TurnInDB(TurnBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TurnResponse(TurnInDB):
    pass
