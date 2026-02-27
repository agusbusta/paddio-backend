from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationUpdate


def create_notification(db: Session, notification: NotificationCreate) -> Notification:
    """Crear una nueva notificación"""
    db_notification = Notification(
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        type=notification.type,
        data=notification.data,
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


def get_user_notifications(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> List[Notification]:
    """Obtener todas las notificaciones de un usuario"""
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_unread_notifications_count(db: Session, user_id: int) -> int:
    """Obtener el conteo de notificaciones no leídas de un usuario"""
    return (
        db.query(Notification)
        .filter(and_(Notification.user_id == user_id, Notification.is_read == False))
        .count()
    )


def get_notification(
    db: Session, notification_id: int, user_id: int
) -> Optional[Notification]:
    """Obtener una notificación específica de un usuario"""
    return (
        db.query(Notification)
        .filter(
            and_(Notification.id == notification_id, Notification.user_id == user_id)
        )
        .first()
    )


def mark_notification_as_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Marcar una notificación como leída"""
    notification = get_notification(db, notification_id, user_id)
    if not notification:
        return False

    notification.is_read = True
    db.commit()
    return True


def mark_all_notifications_as_read(db: Session, user_id: int) -> int:
    """Marcar todas las notificaciones de un usuario como leídas"""
    updated_count = (
        db.query(Notification)
        .filter(and_(Notification.user_id == user_id, Notification.is_read == False))
        .update({"is_read": True})
    )

    db.commit()
    return updated_count


def delete_notification(db: Session, notification_id: int, user_id: int) -> bool:
    """Eliminar una notificación específica de un usuario"""
    notification = get_notification(db, notification_id, user_id)
    if not notification:
        return False

    db.delete(notification)
    db.commit()
    return True


def delete_all_notifications(db: Session, user_id: int) -> int:
    """Eliminar todas las notificaciones de un usuario"""
    deleted_count = (
        db.query(Notification).filter(Notification.user_id == user_id).delete()
    )

    db.commit()
    return deleted_count
