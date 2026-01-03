from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
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
    courts_count: int = Query(1, description="Número de canchas a crear", ge=1, le=20),
    admin_user_id: Optional[int] = Query(None, description="ID del administrador a asignar al club"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Solo admins o super admins pueden crear clubs
    if not (current_user.is_admin or current_user.is_super_admin):
        raise HTTPException(status_code=403, detail="Only admins can create clubs")

    # Si es super admin, puede crear clubs y asignar cualquier admin
    # Si es admin normal, verificar que no tenga ya un club
    admin_user = None
    default_password = None
    
    if current_user.is_super_admin:
        # Super admin puede asignar un admin específico o dejar sin asignar
        if admin_user_id is not None:
            # Verificar que el admin_user_id sea un admin válido
            from app.models.user import User
            admin_user = db.query(User).filter(
                User.id == admin_user_id,
                User.is_admin == True,
                User.is_super_admin == False
            ).first()
            if not admin_user:
                raise HTTPException(status_code=404, detail="Admin user not found")
            # Verificar que el admin no tenga ya un club asignado
            if admin_user.club_id is not None:
                raise HTTPException(status_code=400, detail="Admin already has a club assigned")
            
            # Generar contraseña por defecto para el admin
            # Usar una contraseña segura pero memorable
            alphabet = string.ascii_letters + string.digits + "!@#$%"
            default_password = ''.join(secrets.choice(alphabet) for i in range(12))
            
            # Actualizar la contraseña del admin con la nueva contraseña por defecto
            admin_user.hashed_password = get_password_hash(default_password)
            db.commit()
    else:
        # Admin normal solo puede crear un club para sí mismo
        if current_user.club_id is not None:
            raise HTTPException(status_code=400, detail="Admin already has a club")
        admin_user_id = current_user.id
        admin_user = current_user

    # Crear el club
    created_club = crud.create_club(db=db, club=club, admin_user_id=admin_user_id)
    
    # Enviar email de bienvenida al administrador si se asignó uno
    if admin_user and admin_user_id and default_password:
        try:
            email_sent = email_service.send_admin_welcome_email(
                to_email=admin_user.email,
                admin_name=admin_user.name,
                club_name=created_club.name,
                default_password=default_password
            )
            if not email_sent:
                # Log el error pero no fallar la creación del club
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error enviando email de bienvenida a {admin_user.email}")
        except Exception as e:
            # Log el error pero no fallar la creación del club
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando email de bienvenida a {admin_user.email}: {e}")

    # Crear canchas automáticamente
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


@router.get("/", response_model=List[ClubResponse])
def read_clubs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    clubs = crud.get_clubs(db, skip=skip, limit=limit)
    return clubs


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
