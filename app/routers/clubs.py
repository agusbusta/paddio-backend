from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import secrets
import string

from app.database import get_db
from app.crud import club as crud
from app.schemas.club import ClubResponse, ClubCreate, ClubUpdate
from app.services.auth import get_current_user, get_password_hash
from app.models.user import User
from app.services.email_service import email_service

router = APIRouter()


@router.get("/search")
def search_clubs(
    q: str = Query(..., description="Search query for club name, address, or phone"),
    skip: int = Query(0, description="Number of results to skip"),
    limit: int = Query(100, description="Maximum number of results to return"),
    db: Session = Depends(get_db),
):
    """
    Buscar clubs por nombre, dirección o teléfono.

    Returns a list of clubs that match the search query.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    clubs = crud.search_clubs(db=db, query=q.strip(), skip=skip, limit=limit)

    # Formatear la respuesta según el formato solicitado
    result = []
    for club in clubs:
        result.append(
            {
                "id": club.id,
                "name": club.name,
                "address": club.address,
                "phone": club.phone,
            }
        )

    return result


@router.post("/", response_model=ClubResponse)
def create_club(
    club: ClubCreate,
    courts_count: int = Query(
        0, description="Número de canchas a crear (0 = no crear canchas)", ge=0, le=20
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Solo super admins pueden crear clubs (y sus administradores)
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can create clubs"
        )

    # Verificar que el email del admin no esté en uso
    from app.models.user import User

    existing_user = db.query(User).filter(User.email == club.admin_email).first()
    if existing_user:
        raise HTTPException(
            status_code=400, detail="El email del administrador ya está en uso"
        )

    # Generar contraseña por defecto para el nuevo administrador
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    default_password = "".join(secrets.choice(alphabet) for i in range(12))

    # Crear el administrador primero
    hashed_password = get_password_hash(default_password)
    new_admin = User(
        name=club.admin_name,
        email=club.admin_email,
        phone=club.phone,  # Usar el teléfono del club para el admin
        hashed_password=hashed_password,
        is_admin=True,
        is_super_admin=False,
        is_active=True,
        must_change_password=True,  # Forzar cambio de contraseña en primer login
        created_at=datetime.utcnow(),
    )
    db.add(new_admin)
    db.flush()  # Para obtener el ID del admin antes de crear el club

    # Crear el club directamente (sin admin_user_id todavía)
    from app.models.club import Club

    club_data = club.model_dump(exclude={"admin_name", "admin_email"})
    # El email del club es el mismo que el del administrador
    club_data["email"] = club.admin_email
    # Convertir opening_time y closing_time de time a Time si es necesario
    db_club = Club(**club_data)
    db.add(db_club)
    db.flush()  # Para obtener el ID del club
    db.refresh(db_club)
    created_club = db_club

    # Asignar el club al administrador
    new_admin.club_id = created_club.id
    db.commit()
    db.refresh(new_admin)
    db.refresh(created_club)

    # Enviar email de bienvenida al administrador
    try:
        email_sent = email_service.send_admin_welcome_email(
            to_email=new_admin.email,
            admin_name=new_admin.name,
            club_name=created_club.name,
            default_password=default_password,
        )
        if not email_sent:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Error enviando email de bienvenida a {new_admin.email}")
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error enviando email de bienvenida a {new_admin.email}: {e}")

    # Crear canchas automáticamente solo si se especifica un número mayor a 0
    # Si es 0, el administrador las creará desde su dashboard
    if courts_count > 0:
        try:
            from app.crud import court as court_crud
            from app.schemas.court import CourtCreate

            for i in range(courts_count):
                court_data = CourtCreate(
                    name=f"Cancha {i + 1}",
                    description=f"Cancha {i + 1} del club {created_club.name}",
                    club_id=created_club.id,
                    surface_type="artificial_grass",
                    is_indoor=False,
                    has_lighting=True,
                    is_available=True,
                )
                court_crud.create_court(db=db, court=court_data)
        except Exception as e:
            # Log el error pero no fallar la creación del club
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error creating courts for club {created_club.id}: {e}")

    # Generar estructura de turnos para el club
    try:
        turns_data = crud.generate_turns_data_for_club(db=db, club_id=created_club.id)
        if turns_data:
            # Crear el registro de turnos en la base de datos
            from app.schemas.turn import TurnCreate
            from app.crud import turn as turn_crud

            turn_create = TurnCreate(club_id=created_club.id, turns_data=turns_data)
            turn_crud.create_turn(db=db, turn=turn_create)
    except Exception as e:
        # Log el error pero no fallar la creación del club
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error generating turns data for club {created_club.id}: {e}")

    return created_club


@router.get("/")
def read_clubs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Lista todos los clubs con información de sus administradores.
    """
    clubs = crud.get_clubs(db, skip=skip, limit=limit)

    # Enriquecer con información del administrador
    from app.models.user import User

    result = []
    for club in clubs:
        club_dict = {
            "id": club.id,
            "name": club.name,
            "address": club.address,
            "phone": club.phone,
            "email": club.email,
            "description": club.description,
            "opening_time": (
                club.opening_time.isoformat() if club.opening_time else None
            ),
            "closing_time": (
                club.closing_time.isoformat() if club.closing_time else None
            ),
            "turn_duration_minutes": club.turn_duration_minutes,
            "price_per_turn": club.price_per_turn,
            "monday_open": club.monday_open,
            "tuesday_open": club.tuesday_open,
            "wednesday_open": club.wednesday_open,
            "thursday_open": club.thursday_open,
            "friday_open": club.friday_open,
            "saturday_open": club.saturday_open,
            "sunday_open": club.sunday_open,
            "created_at": club.created_at.isoformat() if club.created_at else None,
            "admin_id": None,
            "admin_name": None,
        }

        # Buscar el administrador asociado a este club
        admin = (
            db.query(User)
            .filter(User.club_id == club.id, User.is_admin == True)
            .first()
        )

        if admin:
            club_dict["admin_id"] = admin.id
            club_dict["admin_name"] = admin.name

        result.append(club_dict)

    return result


@router.get("/{club_id}", response_model=ClubResponse)
def read_club(club_id: int, db: Session = Depends(get_db)):
    db_club = crud.get_club(db, club_id=club_id)
    if db_club is None:
        raise HTTPException(status_code=404, detail="Club not found")
    return db_club


@router.put("/{club_id}", response_model=ClubResponse)
def update_club(club_id: int, club: ClubUpdate, db: Session = Depends(get_db)):
    db_club = crud.update_club(db=db, club_id=club_id, club=club)
    if db_club is None:
        raise HTTPException(status_code=404, detail="Club not found")
    return db_club


@router.delete("/{club_id}")
def delete_club(club_id: int, db: Session = Depends(get_db)):
    success = crud.delete_club(db=db, club_id=club_id)
    if not success:
        raise HTTPException(status_code=404, detail="Club not found")
    return {"message": "Club deleted successfully"}


@router.post("/{club_id}/generate-turns")
def generate_turns_for_club(
    club_id: int,
    days_ahead: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Genera turnos automáticamente para un club.
    """
    # Solo admins pueden generar turnos
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can generate turns")

    # Verificar que el admin tenga un club
    if not current_user.club_id:
        raise HTTPException(
            status_code=400, detail="Admin must have a club to generate turns"
        )

    # Verificar que el club pertenezca al admin
    if club_id != current_user.club_id:
        raise HTTPException(
            status_code=403, detail="Can only generate turns for your own club"
        )

    # Generar estructura de turnos
    try:
        turns_data = crud.generate_turns_data_for_club(db=db, club_id=club_id)
        if turns_data:
            # Crear o actualizar el registro de turnos en la base de datos
            from app.schemas.turn import TurnCreate
            from app.crud import turn as turn_crud

            # Verificar si ya existe un registro de turnos para este club
            existing_turn = turn_crud.get_turns(db=db, club_id=club_id)
            if existing_turn:
                # Actualizar el registro existente
                turn_crud.update_turn(
                    db=db,
                    turn_id=existing_turn[0].id,
                    turn=TurnCreate(club_id=club_id, turns_data=turns_data),
                )
                return {
                    "message": f"Updated turns data for club {club_id} with {len(turns_data['turns'])} turn slots"
                }
            else:
                # Crear nuevo registro
                turn_create = TurnCreate(club_id=club_id, turns_data=turns_data)
                turn_crud.create_turn(db=db, turn=turn_create)
                return {
                    "message": f"Generated turns data for club {club_id} with {len(turns_data['turns'])} turn slots"
                }
        else:
            return {"message": "No turns data generated"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating turns data: {str(e)}"
        )
