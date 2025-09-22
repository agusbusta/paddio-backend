from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, time
from enum import Enum


class CourtType(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class CourtSurface(str, Enum):
    ARTIFICIAL_GRASS = "artificial_grass"
    CEMENT = "cement"
    CARPET = "carpet"


class MatchStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ClubBase(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    description: Optional[str] = None

    # Horarios del club
    opening_time: time  # Hora de apertura (ej: "08:00")
    closing_time: time  # Hora de cierre (ej: "22:00")
    turn_duration_minutes: int = 90  # Duración de cada turno en minutos (1.5 horas)
    price_per_turn: int = 0  # Precio por turno en centavos

    # Días de la semana que está abierto
    monday_open: bool = True
    tuesday_open: bool = True
    wednesday_open: bool = True
    thursday_open: bool = True
    friday_open: bool = True
    saturday_open: bool = True
    sunday_open: bool = True


class ClubCreate(ClubBase):
    pass


class ClubUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None


class ClubInDB(ClubBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ClubResponse(ClubInDB):
    pass


class StadiumBase(BaseModel):
    name: str
    club_id: int


class StadiumCreate(StadiumBase):
    pass


class CourtBase(BaseModel):
    stadium_id: int
    type: CourtType
    surface: CourtSurface


class CourtCreate(CourtBase):
    pass


class MatchBase(BaseModel):
    court_id: int
    start_time: datetime
    end_time: datetime
    status: MatchStatus = MatchStatus.AVAILABLE


class MatchCreate(MatchBase):
    pass


class MatchUpdate(BaseModel):
    status: Optional[MatchStatus] = None


class MatchResponse(MatchBase):
    id: int
    creator_id: int
    players: List[int]

    class Config:
        from_attributes = True
