from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TurnStatus(str, Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TurnBase(BaseModel):
    court_id: int
    start_time: datetime
    end_time: datetime
    price: int = Field(..., description="Price in cents")
    status: TurnStatus = TurnStatus.AVAILABLE


class TurnCreate(TurnBase):
    pass


class TurnUpdate(BaseModel):
    status: Optional[TurnStatus] = None
    price: Optional[int] = None


class TurnInDB(TurnBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Turn(TurnInDB):
    pass
