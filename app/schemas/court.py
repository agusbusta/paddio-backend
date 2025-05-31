from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CourtBase(BaseModel):
    name: str
    description: Optional[str] = None
    stadium_id: int
    surface_type: str
    is_indoor: bool = False
    is_available: bool = True


class CourtCreate(CourtBase):
    pass


class CourtUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    surface_type: Optional[str] = None
    is_indoor: Optional[bool] = None
    is_available: Optional[bool] = None


class CourtInDB(CourtBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CourtResponse(CourtInDB):
    pass
