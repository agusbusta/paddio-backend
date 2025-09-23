from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.booking import Booking, BookingStatus
from app.schemas.booking import BookingCreate, BookingUpdate


def get_booking(db: Session, booking_id: int) -> Optional[Booking]:
    return db.query(Booking).filter(Booking.id == booking_id).first()


def get_bookings(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    pregame_turn_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
) -> List[Booking]:
    query = db.query(Booking)

    if user_id:
        query = query.filter(Booking.user_id == user_id)
    if pregame_turn_id:
        query = query.filter(Booking.pregame_turn_id == pregame_turn_id)
    if status:
        query = query.filter(Booking.status == status)

    return query.offset(skip).limit(limit).all()


def create_booking(db: Session, booking: BookingCreate) -> Booking:
    db_booking = Booking(
        pregame_turn_id=booking.pregame_turn_id,
        user_id=booking.user_id,
        status=booking.status,
        payment_status=booking.payment_status,
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking


def update_booking(
    db: Session, booking_id: int, booking: BookingUpdate
) -> Optional[Booking]:
    db_booking = get_booking(db, booking_id)
    if not db_booking:
        return None

    update_data = booking.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_booking, field, value)

    db.commit()
    db.refresh(db_booking)
    return db_booking


def delete_booking(db: Session, booking_id: int) -> bool:
    db_booking = get_booking(db, booking_id)
    if not db_booking:
        return False

    db.delete(db_booking)
    db.commit()
    return True
