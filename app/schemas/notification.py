from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class NotificationBase(BaseModel):
    title: str
    message: str
    type: str
    data: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationsListResponse(BaseModel):
    success: bool
    notifications: List[NotificationResponse]
    unread_count: int


class NotificationActionResponse(BaseModel):
    success: bool
    message: str
