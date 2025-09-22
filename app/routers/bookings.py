from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.crud import booking as crud
from app.schemas.booking import Booking, BookingCreate, BookingUpdate
from app.models.booking import BookingStatus
from app.services.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=Booking)
def create_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verificar que el usuario esté reservando para sí mismo
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only make bookings for yourself"
        )

    return crud.create_booking(db=db, booking=booking)


@router.get("/", response_model=List[Booking])
def read_bookings(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[int] = None,
    turn_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
    db: Session = Depends(get_db),
):
    bookings = crud.get_bookings(
        db=db, skip=skip, limit=limit, user_id=user_id, turn_id=turn_id, status=status
    )
    return bookings


@router.get("/{booking_id}", response_model=Booking)
def read_booking(booking_id: int, db: Session = Depends(get_db)):
    db_booking = crud.get_booking(db=db, booking_id=booking_id)
    if db_booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return db_booking


@router.put("/{booking_id}", response_model=Booking)
def update_booking(
    booking_id: int, booking: BookingUpdate, db: Session = Depends(get_db)
):
    db_booking = crud.update_booking(db=db, booking_id=booking_id, booking=booking)
    if db_booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return db_booking


@router.delete("/{booking_id}")
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    success = crud.delete_booking(db=db, booking_id=booking_id)
    if not success:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"message": "Booking deleted successfully"}
