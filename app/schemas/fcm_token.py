from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FCMTokenBase(BaseModel):
    token: str
    device_type: Optional[str] = None


class FCMTokenCreate(FCMTokenBase):
    pass


class FCMTokenUpdate(BaseModel):
    token: Optional[str] = None
    device_type: Optional[str] = None
    is_active: Optional[bool] = None


class FCMTokenInDB(FCMTokenBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FCMTokenResponse(FCMTokenInDB):
    pass


class NotificationRequest(BaseModel):
    title: str
    body: str
    data: Optional[dict] = None


class NotificationResponse(BaseModel):
    success: bool
    message: str
    sent_count: Optional[int] = None
    failed_count: Optional[int] = None
