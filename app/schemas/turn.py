from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum


class TurnDataItem(BaseModel):
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
