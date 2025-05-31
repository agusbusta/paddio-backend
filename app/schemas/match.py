from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MatchBase(BaseModel):
    court_id: int
    start_time: datetime
    end_time: datetime
    status: str = "scheduled"
    score: Optional[str] = None


class MatchCreate(MatchBase):
    pass


class MatchUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    score: Optional[str] = None


class MatchInDB(MatchBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class MatchResponse(MatchInDB):
    pass
