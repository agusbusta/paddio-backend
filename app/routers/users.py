from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import traceback
import json
import logging
from fastapi.responses import JSONResponse

from app.database import get_db
from app.crud import user as crud
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    UserCreate,
    AdminResponse,
    AdminsResponse,
    AdminCreate,
    AdminUpdate,
    AdminSchema,
)
from app.enums.user_category import UserCategory
from app.services.auth import get_current_user, get_password_hash
from app.models.user import User

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/me")
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Obtener perfil completo del usuario actual"""
    print(
        f"🔍 DEBUG GET /users/me: Usuario actual - ID: {current_user.id}, Name: {current_user.name}, Email: {current_user.email}"
    )
    print(
        f"📊 DEBUG GET /users/me: is_profile_complete: {current_user.is_profile_complete}, category: {current_user.category}"
    )

    # Devolver perfil completo del usuario
    user_response = {
        "id": str(current_user.id),
        "name": current_user.name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "is_profile_complete": current_user.is_profile_complete,
        "category": current_user.category,
        "gender": current_user.gender,
        "height": current_user.height,
        "dominant_hand": current_user.dominant_hand,
        "preferred_side": current_user.preferred_side,
        "preferred_court_type": current_user.preferred_court_type,
        "city": current_user.city,
        "province": current_user.province,
        "photoUrl": current_user.profile_image_url,
        "phoneNumber": current_user.phone,
        "isActive": current_user.is_active,
        "createdAt": (
            current_user.created_at.isoformat() if current_user.created_at else None
        ),
    }

    print(f"📤 DEBUG GET /users/me: Enviando respuesta con user: {user_response}")

    return {
        "success": True,
        "user": user_response,
    }


@router.get("/super-admins")
def get_super_admins(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Lista todos los super administradores.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Obtener super administradores
    super_admins = (
        db.query(User).filter(User.is_super_admin == True).all()
    )
    super_admin_list = []

    for super_admin in super_admins:
        super_admin_data = {
            "id": super_admin.id,
            "name": super_admin.name,
            "last_name": super_admin.last_name,
            "email": super_admin.email,
            "phone": super_admin.phone if hasattr(super_admin, "phone") else None,
            "is_active": (
                True if hasattr(super_admin, "is_active") and super_admin.is_active else False
            ),
            "created_at": (
                super_admin.created_at.isoformat()
                if hasattr(super_admin, "created_at") and super_admin.created_at
                else datetime.utcnow().isoformat()
            ),
            "role": "super_admin",
        }
        super_admin_list.append(super_admin_data)

    return {"super_admins": super_admin_list}


@router.get("/admins")
def get_admins(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Lista todos los administradores.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Obtener administradores
    admins = (
        db.query(User).filter(User.is_admin == True, User.is_super_admin == False).all()
    )
    admin_list = []

    for admin in admins:
        # Formato exacto que espera el frontend
        admin_data = {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "phone": admin.phone if hasattr(admin, "phone") else None,
            "club_id": None,  # Ajustar si existe relación con clubes
            "club_name": None,  # Ajustar si existe relación con clubes
            "is_active": (
                True if hasattr(admin, "is_active") and admin.is_active else False
            ),
            "created_at": (
                admin.created_at.isoformat()
                if hasattr(admin, "created_at") and admin.created_at
                else datetime.utcnow().isoformat()
            ),
            "updated_at": None,  # Ajustar si existe campo updated_at
            "role": "admin",
        }
        admin_list.append(admin_data)

    # Devolver exactamente la estructura que espera el frontend
    return {"admins": admin_list}


@router.get("/admins/{admin_id}")
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un administrador específico por ID.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Formato exacto que espera el frontend
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone if hasattr(admin, "phone") else None,
        "club_id": None,  # Ajustar si existe relación con clubes
        "club_name": None,  # Ajustar si existe relación con clubes
        "is_active": True if hasattr(admin, "is_active") and admin.is_active else False,
        "created_at": (
            admin.created_at.isoformat()
            if hasattr(admin, "created_at") and admin.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": None,  # Ajustar si existe campo updated_at
        "role": "admin",
    }

    return {"admin": admin_data}


@router.post("/admins")
def create_admin(
    admin_data: dict,  # Usar dict en lugar de modelo Pydantic para más flexibilidad
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea un nuevo administrador.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Verificar datos requeridos
    if not all(key in admin_data for key in ["name", "email", "password"]):
        raise HTTPException(status_code=400, detail="Faltan campos requeridos")

    # Verificar si el email ya existe
    existing = db.query(User).filter(User.email == admin_data["email"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Crear el administrador
    hashed_password = get_password_hash(admin_data["password"])
    new_admin = User(
        name=admin_data["name"],
        email=admin_data["email"],
        phone=admin_data.get("phone"),
        hashed_password=hashed_password,
        is_admin=True,
        is_super_admin=False,
        is_active=True,
    )

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    # Formato exacto que espera el frontend
    response_data = {
        "id": new_admin.id,
        "name": new_admin.name,
        "email": new_admin.email,
        "phone": new_admin.phone,
        "club_id": None,
        "club_name": None,
        "is_active": new_admin.is_active,
        "created_at": (
            new_admin.created_at.isoformat()
            if hasattr(new_admin, "created_at") and new_admin.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": None,
        "role": "admin",
    }

    return {"admin": response_data}


@router.put("/admins/{admin_id}")
def update_admin(
    admin_id: int,
    admin_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Actualiza un administrador existente.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Actualizar campos
    if "name" in admin_data:
        admin.name = admin_data["name"]
    if "email" in admin_data:
        # Verificar si el nuevo email ya existe
        if admin_data["email"] != admin.email:
            existing = db.query(User).filter(User.email == admin_data["email"]).first()
            if existing:
                raise HTTPException(
                    status_code=400, detail="El email ya está registrado"
                )
        admin.email = admin_data["email"]
    if "phone" in admin_data:
        admin.phone = admin_data["phone"]
    if "is_active" in admin_data:
        admin.is_active = admin_data["is_active"]

    db.commit()
    db.refresh(admin)

    # Formato exacto que espera el frontend
    response_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,
        "club_name": None,
        "is_active": admin.is_active,
        "created_at": (
            admin.created_at.isoformat()
            if hasattr(admin, "created_at") and admin.created_at
            else datetime.utcnow().isoformat()
        ),
        "updated_at": None,
        "role": "admin",
    }

    return {"admin": response_data}


@router.get("/admins/{admin_id}", response_model=AdminResponse)
def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Registro público de jugadores (usuarios normales).
    """
    # Verificar si el email ya existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El email ya está en uso")

    # Crear usuario normal (no admin)
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        name=user_data.name,
        email=user_data.email,
        phone=user_data.phone,
        hashed_password=hashed_password,
        is_admin=False,  # Jugador normal
        is_super_admin=False,
        is_active=True,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@router.post(
    "/admins", response_model=AdminResponse, status_code=status.HTTP_201_CREATED
)
def create_admin(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    # Verificar si el email ya existe
    existing_admin = db.query(User).filter(User.email == admin_data.email).first()
    if existing_admin:
        raise HTTPException(status_code=400, detail="El email ya está en uso")

    # Crear hash de la contraseña
    hashed_password = get_password_hash(admin_data.password)

    # Crear el administrador
    new_admin = User(
        name=admin_data.name,
        email=admin_data.email,
        phone=admin_data.phone,
        hashed_password=hashed_password,
        is_admin=True,
        is_super_admin=False,
        is_active=True,
        created_at=datetime.utcnow(),
    )

    # Si se asigna un club al crear el admin, asignarlo
    club = None
    if admin_data.club_id:
        from app.crud import club as club_crud
        club = club_crud.get_club(db, admin_data.club_id)
        if not club:
            raise HTTPException(status_code=404, detail="Club not found")
        # Verificar que el club no tenga ya un admin asignado
        if club.admin_user_id is not None:
            raise HTTPException(status_code=400, detail="Club already has an admin assigned")
        new_admin.club_id = admin_data.club_id

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    # Si se asignó un club, enviar email de bienvenida al administrador
    if club and admin_data.club_id:
        try:
            from app.services.email_service import email_service
            email_sent = email_service.send_admin_welcome_email(
                to_email=new_admin.email,
                admin_name=new_admin.name,
                club_name=club.name,
                default_password=admin_data.password  # Usar la contraseña ingresada
            )
            if not email_sent:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error enviando email de bienvenida a {new_admin.email}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error enviando email de bienvenida a {new_admin.email}: {e}")

    # Convertir el usuario a un esquema AdminSchema
    admin_response_data = {
        "id": new_admin.id,
        "name": new_admin.name,
        "email": new_admin.email,
        "phone": new_admin.phone,
        "club_id": new_admin.club_id,
        "club_name": club.name if club else None,
        "is_active": new_admin.is_active,
        "created_at": new_admin.created_at,
        "updated_at": None,
        "role": "admin",
    }

    return {"admin": admin_response_data}


@router.put("/admins/{admin_id}", response_model=AdminResponse)
def update_admin(
    admin_id: int,
    admin_data: AdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Verificar si el email ya existe y no es del mismo admin
    if admin_data.email != admin.email:
        existing_admin = db.query(User).filter(User.email == admin_data.email).first()
        if existing_admin:
            raise HTTPException(status_code=400, detail="El email ya está en uso")

    # Actualizar datos
    admin.name = admin_data.name
    admin.email = admin_data.email
    admin.phone = admin_data.phone
    admin.is_active = admin_data.is_active

    db.commit()
    db.refresh(admin)

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    db.delete(admin)
    db.commit()

    return None


@router.patch("/admins/{admin_id}/toggle-status", response_model=AdminResponse)
def toggle_admin_status(
    admin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para esta acción"
        )

    admin = (
        db.query(User)
        .filter(
            User.id == admin_id, User.is_admin == True, User.is_super_admin == False
        )
        .first()
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # Cambiar estado
    admin.is_active = not admin.is_active

    db.commit()
    db.refresh(admin)

    # Convertir el usuario a un esquema AdminSchema
    admin_data = {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "phone": admin.phone,
        "club_id": None,  # Ajusta según tu modelo
        "club_name": None,  # Ajusta según tu modelo
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "updated_at": None,  # Ajusta según tu modelo
        "role": "admin",
    }

    return {"admin": admin_data}


@router.get("/", response_model=List[UserResponse])
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all users. Requires authentication.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific user by ID. Requires authentication.
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a user. Requires authentication and user can only update their own profile.
    """
    print(f"🔍 DEBUG PUT /users/{user_id}: Actualizando usuario {user_id}")
    print(
        f"📊 DEBUG PUT /users/{user_id}: Datos recibidos: {user.model_dump(exclude_unset=True)}"
    )

    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to update other users"
        )

    # Validar cambio de género si el usuario está en un turno mixto activo
    if user.gender is not None and user.gender != current_user.gender:
        from app.models.pregame_turn import PregameTurn
        from sqlalchemy import and_, or_
        from datetime import date as date_type

        # Buscar turnos mixtos activos donde el usuario participa
        active_mixed_turns = (
            db.query(PregameTurn)
            .filter(
                and_(
                    PregameTurn.is_mixed_match == "true",
                    or_(
                        PregameTurn.player1_id == user_id,
                        PregameTurn.player2_id == user_id,
                        PregameTurn.player3_id == user_id,
                        PregameTurn.player4_id == user_id,
                    ),
                    PregameTurn.status.in_(["PENDING", "READY_TO_PLAY"]),
                    PregameTurn.date >= datetime.now().date(),
                )
            )
            .all()
        )

        if active_mixed_turns:
            raise HTTPException(
                status_code=400,
                detail="No podés cambiar tu género mientras participás en un partido mixto activo.",
            )

    try:
        db_user = crud.update_user(db=db, user_id=user_id, user=user)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        # CRÍTICO: Verificar que los datos se actualizaron correctamente antes de calcular completitud
        print(f"🔍 DEBUG PUT /users/{user_id}: Usuario antes de calcular completitud:")
        print(f"   - name: {db_user.name}")
        print(f"   - last_name: {db_user.last_name}")
        print(f"   - gender: {db_user.gender}")
        print(f"   - height: {db_user.height}")
        print(f"   - dominant_hand: {db_user.dominant_hand}")
        print(f"   - preferred_side: {db_user.preferred_side}")
        print(f"   - preferred_court_type: {db_user.preferred_court_type}")
        print(f"   - city: {db_user.city}")
        print(f"   - category: {db_user.category}")

        # Calcular is_profile_complete después de la actualización
        # UNA SOLA FUENTE DE VERDAD: usar la función común de profile_utils
        from app.utils.profile_utils import calculate_profile_completeness

        is_complete = calculate_profile_completeness(db_user)
        db_user.is_profile_complete = is_complete

        db.commit()
        db.refresh(db_user)

        print(
            f"✅ DEBUG PUT /users/{user_id}: Usuario actualizado - is_profile_complete: {is_complete}"
        )
        print(
            f"📊 DEBUG PUT /users/{user_id}: Datos finales: name={db_user.name}, last_name={db_user.last_name}, gender={db_user.gender}, is_profile_complete={is_complete}"
        )

        # CRÍTICO: Verificar que is_profile_complete se guardó correctamente
        if db_user.is_profile_complete != is_complete:
            print(
                f"⚠️ WARNING PUT /users/{user_id}: is_profile_complete no coincide! Esperado: {is_complete}, Obtenido: {db_user.is_profile_complete}"
            )
            # Forzar el valor correcto
            db_user.is_profile_complete = is_complete
            db.commit()
            db.refresh(db_user)

        return db_user
    except HTTPException:
        raise
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            f"❌ ERROR PUT /users/{user_id}: Error al actualizar usuario: {str(e)}"
        )
        logger.error(f"   Tipo de error: {type(e).__name__}")
        import traceback

        logger.error(f"   Traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error interno al actualizar perfil: {str(e)}"
        )


@router.get("/{user_id}/diagnose")
def diagnose_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint de diagnóstico para verificar el estado del perfil de un usuario.
    Útil para identificar problemas con usuarios específicos.
    """
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to diagnose other users"
        )

    db_user = crud.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.utils.profile_utils import calculate_profile_completeness

    # Calcular completitud
    calculated_completeness = calculate_profile_completeness(db_user)

    # Información detallada
    diagnosis = {
        "user_id": db_user.id,
        "email": db_user.email,
        "name": db_user.name,
        "last_name": db_user.last_name,
        "is_profile_complete_in_db": db_user.is_profile_complete,
        "calculated_is_profile_complete": calculated_completeness,
        "fields_status": {
            "name": {
                "value": db_user.name,
                "is_complete": db_user.name is not None and db_user.name != "",
            },
            "last_name": {
                "value": db_user.last_name,
                "is_complete": db_user.last_name is not None
                and db_user.last_name != "",
            },
            "gender": {
                "value": db_user.gender,
                "is_complete": db_user.gender is not None and db_user.gender != "",
            },
            "height": {
                "value": db_user.height,
                "is_complete": db_user.height is not None,
            },
            "dominant_hand": {
                "value": db_user.dominant_hand,
                "is_complete": db_user.dominant_hand is not None
                and db_user.dominant_hand != "",
            },
            "preferred_side": {
                "value": db_user.preferred_side,
                "is_complete": db_user.preferred_side is not None
                and db_user.preferred_side != "",
            },
            "preferred_court_type": {
                "value": db_user.preferred_court_type,
                "is_complete": db_user.preferred_court_type is not None
                and db_user.preferred_court_type != "",
            },
            "city": {
                "value": db_user.city,
                "is_complete": db_user.city is not None and db_user.city != "",
            },
            "category": {
                "value": db_user.category,
                "is_complete": db_user.category is not None and db_user.category != "",
            },
        },
        "mismatch_detected": db_user.is_profile_complete != calculated_completeness,
        "recommendation": (
            "Corregir is_profile_complete en la base de datos"
            if db_user.is_profile_complete != calculated_completeness
            else "Perfil correcto"
        ),
    }

    # Si hay un mismatch, ofrecer corregirlo automáticamente
    if diagnosis["mismatch_detected"]:
        diagnosis["auto_fix_available"] = True
        diagnosis["auto_fix_message"] = (
            "Se puede corregir automáticamente llamando a PUT /users/{user_id}/fix-profile"
        )

    return diagnosis


@router.put("/{user_id}/fix-profile")
def fix_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Corrige el estado is_profile_complete de un usuario basándose en el cálculo actual.
    """
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to fix other users"
        )

    db_user = crud.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.utils.profile_utils import calculate_profile_completeness

    old_value = db_user.is_profile_complete
    new_value = calculate_profile_completeness(db_user)

    if old_value == new_value:
        return {
            "success": True,
            "message": "El perfil ya está correcto",
            "is_profile_complete": new_value,
        }

    db_user.is_profile_complete = new_value
    db.commit()
    db.refresh(db_user)

    return {
        "success": True,
        "message": f"Perfil corregido: is_profile_complete cambió de {old_value} a {new_value}",
        "old_value": old_value,
        "new_value": new_value,
        "is_profile_complete": db_user.is_profile_complete,
    }


@router.post("/test-problematic-users")
def test_problematic_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint de prueba para diagnosticar y corregir usuarios problemáticos.
    Solo para administradores.
    """
    if not current_user.is_admin and not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Solo administradores pueden usar este endpoint"
        )

    problematic_emails = ["jugador4@test.com", "jugador@test.com"]
    results = []

    for email in problematic_emails:
        user = crud.get_user_by_email(db, email)
        if not user:
            results.append(
                {
                    "email": email,
                    "status": "not_found",
                    "message": "Usuario no encontrado",
                }
            )
            continue

        from app.utils.profile_utils import calculate_profile_completeness

        # Diagnóstico completo
        calculated_completeness = calculate_profile_completeness(user)
        stored_completeness = user.is_profile_complete

        # Detectar campos problemáticos
        problem_fields = []
        if not user.name or user.name == "":
            problem_fields.append("name")
        if not user.last_name or user.last_name == "":
            problem_fields.append("last_name")
        if not user.gender or user.gender == "":
            problem_fields.append("gender")
        if user.height is None:
            problem_fields.append("height")
        if not user.dominant_hand or user.dominant_hand == "":
            problem_fields.append("dominant_hand")
        if not user.preferred_side or user.preferred_side == "":
            problem_fields.append("preferred_side")
        if not user.preferred_court_type or user.preferred_court_type == "":
            problem_fields.append("preferred_court_type")
        if not user.city or user.city == "":
            problem_fields.append("city")
        if not user.category or user.category == "":
            problem_fields.append("category")

        result = {
            "email": email,
            "user_id": user.id,
            "status": "found",
            "stored_is_profile_complete": stored_completeness,
            "calculated_is_profile_complete": calculated_completeness,
            "mismatch": stored_completeness != calculated_completeness,
            "problem_fields": problem_fields,
            "all_fields": {
                "name": user.name,
                "last_name": user.last_name,
                "gender": user.gender,
                "height": user.height,
                "dominant_hand": user.dominant_hand,
                "preferred_side": user.preferred_side,
                "preferred_court_type": user.preferred_court_type,
                "city": user.city,
                "category": user.category,
            },
        }

        # Intentar corregir si hay mismatch
        if stored_completeness != calculated_completeness:
            try:
                user.is_profile_complete = calculated_completeness
                db.commit()
                db.refresh(user)
                result["fixed"] = True
                result["fix_message"] = (
                    f"Corregido: {stored_completeness} -> {calculated_completeness}"
                )
            except Exception as e:
                result["fixed"] = False
                result["fix_error"] = str(e)
        else:
            result["fixed"] = False
            result["fix_message"] = "No se requiere corrección"

        results.append(result)

    return {
        "success": True,
        "results": results,
        "summary": {
            "total_tested": len(problematic_emails),
            "found": len([r for r in results if r.get("status") == "found"]),
            "not_found": len([r for r in results if r.get("status") == "not_found"]),
            "fixed": len([r for r in results if r.get("fixed") == True]),
        },
    }


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a user. Requires authentication and admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Not enough permissions to delete users"
        )

    success = crud.delete_user(db=db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}


@router.put("/category")
async def update_user_category(
    category: UserCategory,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualizar solo la categoría del usuario"""
    try:
        # Actualizar la categoría del usuario
        current_user.category = category.value
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

        return {
            "success": True,
            "message": f"Categoría actualizada a {category.value}",
            "category": current_user.category,
        }
    except Exception as e:
        logger.error(f"Error updating user category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar la categoría",
        )
