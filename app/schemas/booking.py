from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BookingBase(BaseModel):
    turn_id: int
    user_id: int
    status: BookingStatus = BookingStatus.PENDING
    payment_status: str = "pending"


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    status: Optional[BookingStatus] = None
    payment_status: Optional[str] = None


class BookingInDB(BookingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Booking(BookingInDB):
    pass
