from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum


class PregameTurnStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PENDING = "PENDING"
    READY_TO_PLAY = "READY_TO_PLAY"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PregameTurnBase(BaseModel):
    turn_id: int
    court_id: int
    date: datetime
    start_time: str  # Formato "HH:MM"
    end_time: str  # Formato "HH:MM"
    price: int  # Precio en centavos
    status: PregameTurnStatus = PregameTurnStatus.AVAILABLE
    player1_id: Optional[int] = None
    player2_id: Optional[int] = None
    player3_id: Optional[int] = None
    player4_id: Optional[int] = None
    player_side: Optional[str] = None  # "reves" o "drive"
    player_court_position: Optional[str] = None  # "izquierda" o "derecha"


class PregameTurnCreate(PregameTurnBase):
    pass


class PregameTurnUpdate(BaseModel):
    status: Optional[PregameTurnStatus] = None
    player1_id: Optional[int] = None
    player2_id: Optional[int] = None
    player3_id: Optional[int] = None
    player4_id: Optional[int] = None
    player_side: Optional[str] = None
    player_court_position: Optional[str] = None


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
