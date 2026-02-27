from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional

from app.models.booking import Booking, BookingStatus
from app.models.pregame_turn import PregameTurn, PregameTurnStatus
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
    """
    Crea una reserva con validación de concurrencia.

    CRÍTICO: Usa SELECT FOR UPDATE para prevenir condiciones de carrera.
    Valida que:
    1. El pregame_turn existe
    2. El pregame_turn está disponible (no cancelado/completado)
    3. El usuario no tiene ya una reserva activa para este turno
    4. El turno no está completo (máximo 4 jugadores)
    5. El usuario no está ya en el turno como jugador

    IMPORTANTE: Toda la validación y creación se realiza dentro de una transacción
    con bloqueos pesimistas para prevenir reservas simultáneas.
    """
    from fastapi import HTTPException

    # CRÍTICO: Bloquear el pregame_turn con SELECT FOR UPDATE para prevenir condiciones de carrera
    # Esto asegura que solo una transacción puede procesar la reserva a la vez
    pregame_turn = (
        db.query(PregameTurn)
        .filter(PregameTurn.id == booking.pregame_turn_id)
        .with_for_update(
            nowait=False
        )  # Bloqueo de fila - previene condiciones de carrera
        .first()
    )

    if not pregame_turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    # Validar que el turno no esté cancelado o completado
    if pregame_turn.status in [
        PregameTurnStatus.CANCELLED,
        PregameTurnStatus.COMPLETED,
    ]:
        raise HTTPException(status_code=400, detail="Turno no disponible")

    # Validar que el usuario no tenga ya una reserva activa para este turno
    # CRÍTICO: También bloquear esta consulta para prevenir condiciones de carrera
    existing_booking = (
        db.query(Booking)
        .filter(
            and_(
                Booking.pregame_turn_id == booking.pregame_turn_id,
                Booking.user_id == booking.user_id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
            )
        )
        .with_for_update(nowait=False)  # Bloquear también las reservas existentes
        .first()
    )

    if existing_booking:
        raise HTTPException(status_code=400, detail="Turno no disponible")

    # Validar que el usuario no esté ya en el turno como jugador
    if (
        pregame_turn.player1_id == booking.user_id
        or pregame_turn.player2_id == booking.user_id
        or pregame_turn.player3_id == booking.user_id
        or pregame_turn.player4_id == booking.user_id
    ):
        raise HTTPException(status_code=400, detail="Turno no disponible")

    # Validar que el turno no esté completo (máximo 4 jugadores)
    players_count = sum(
        [
            1
            for player_id in [
                pregame_turn.player1_id,
                pregame_turn.player2_id,
                pregame_turn.player3_id,
                pregame_turn.player4_id,
            ]
            if player_id is not None
        ]
    )

    # CRÍTICO: Bloquear también las reservas activas al contarlas
    # Esto previene que otra transacción cree una reserva entre el conteo y la creación
    active_bookings = (
        db.query(Booking)
        .filter(
            and_(
                Booking.pregame_turn_id == booking.pregame_turn_id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
            )
        )
        .with_for_update(nowait=False)  # Bloquear todas las reservas activas
        .all()
    )

    active_bookings_count = len(active_bookings)
    total_participants = players_count + active_bookings_count

    # CRÍTICO: Validar nuevamente la disponibilidad justo antes de crear la reserva
    # Esto asegura que ningún otro usuario haya reservado entre la validación y la creación
    if total_participants >= 4:
        raise HTTPException(status_code=400, detail="Turno no disponible")

    # Validar que el turno sigue disponible (no fue cancelado por otra transacción)
    db.refresh(pregame_turn)
    if pregame_turn.status in [
        PregameTurnStatus.CANCELLED,
        PregameTurnStatus.COMPLETED,
    ]:
        raise HTTPException(status_code=400, detail="Turno no disponible")

    # Crear la reserva
    db_booking = Booking(
        pregame_turn_id=booking.pregame_turn_id,
        user_id=booking.user_id,
        court_id=pregame_turn.court_id,  # Establecer court_id desde el pregame_turn
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
