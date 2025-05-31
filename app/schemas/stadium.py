from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StadiumBase(BaseModel):
    name: str
    description: Optional[str] = None
    club_id: int


class StadiumCreate(StadiumBase):
    pass


class StadiumUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class StadiumInDB(StadiumBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class StadiumResponse(StadiumInDB):
    pass
